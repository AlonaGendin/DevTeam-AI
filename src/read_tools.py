"""

כלים 1–3: קריאת משימות, קריאת חברי צוות וחישוב עומס
הכלים משתמשים במנגנון אימות הקלט המשותף

"""

from decimal import Decimal
from jsonschema import ValidationError as SchemaValidationError, validate
from src.write_tools import build_output_schema, validate_project_inputs, validate_project_inputs_tool


# פונקציות עזר לבניית חוזי הכלים ותוצאותיהם
def object_schema(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": False,
    }


def array_schema(items, **limits):
    return {"type": "array", "items": items, **limits}


def github_issues_error(error_type, message, *, retryable=False):
    return {
        "status": "error",
        "data": None,
        "error": {
            "type": error_type,
            "message": message,
            "retryable": retryable,
        },
    }


def success(data):
    return {"status": "ok", "data": data, "error": None}


def permissions(access, side_effects="none", requires_approval=False):
    return {
        "access": access,
        "side_effects": side_effects,
        "requires_human_approval": requires_approval,
        "allowed_caller": (
            "agent (only after human approval)" if requires_approval else "agent"
        ),
    }


TEXT = {"type": "string"}


NONBLANK_TEXT = {"type": "string", "pattern": r"\S"}


HOURS = {"type": "number", "minimum": 0}


ISSUE_ID = {"type": "integer", "minimum": 1}


NULLABLE_TEXT = {"type": ["string", "null"]}


REPO_FIELDS = {
    "repo_owner": {"type": "string", "minLength": 1, "maxLength": 50},
    "repo_name": {"type": "string", "minLength": 1, "maxLength": 100},
}


# כלי 1 – קריאת משימות מהמאגר המורשה
MAX_READ_ATTEMPTS = 3


READ_TIMEOUT_SECONDS = 3


get_github_issues_tool = {
    "name": "get_github_issues",
    "description": "Read existing issues in the project's GitHub repository.",
    "input_schema": object_schema(
        {
            "repo_owner": {
                **REPO_FIELDS["repo_owner"],
                "pattern": r"^[A-Za-z0-9-]+$",
            },
            "repo_name": {
                **REPO_FIELDS["repo_name"],
                "pattern": r"^[A-Za-z0-9_.-]+$",
            },
            "state": {
                "type": "string",
                "enum": ["open", "closed", "all"],
                "default": "open",
            },
        },
        required=["repo_owner", "repo_name"],
    ),
    "output_schema": build_output_schema({
        "issues": array_schema(object_schema({
            "id": ISSUE_ID,
            "title": TEXT,
            "assignees": array_schema(TEXT),
        })),
    }),
    "permissions": permissions("read"),
}


def get_github_issues(inputs, client, allowed_repo):
    try:
        validate(instance=inputs, schema=get_github_issues_tool["input_schema"])
    except SchemaValidationError as error:
        return github_issues_error("invalid_input", error.message)

    owner = inputs["repo_owner"]
    repo = inputs["repo_name"]
    state = inputs.get("state", "open")

    requested_repo = (owner.casefold(), repo.casefold())
    configured_repo = tuple(part.casefold() for part in allowed_repo)

    if requested_repo != configured_repo:
        return github_issues_error(
            "permission_denied",
            "Read access is limited to the configured project repository.",
        )

    for attempt in range(1, MAX_READ_ATTEMPTS + 1):
        try:
            issues = client.list_issues(
                repo_owner=owner,
                repo_name=repo,
                state=state,
                timeout=READ_TIMEOUT_SECONDS,
            )
        except (TimeoutError, ConnectionError) as error:
            if attempt < MAX_READ_ATTEMPTS:
                continue
            return github_issues_error(
                "transient_failure", str(error), retryable=True
            )

        result = success({"issues": issues})

        try:
            validate(
                instance=result,
                schema=get_github_issues_tool["output_schema"],
            )
        except SchemaValidationError as error:
            return github_issues_error("invalid_output", error.message)

        return result


# כלי 2 – קריאת חברי צוות וזמינות
get_team_members_tool = {
    "name": "get_team_members",
    "description": "Read team members and configured availability for the active project.",
    "input_schema": object_schema({"project_id": NONBLANK_TEXT}),
    "output_schema": build_output_schema({
        "members": array_schema(object_schema({
            "login": NONBLANK_TEXT,
            "hours": {"type": ["number", "null"], "minimum": 0},
        })),
        "missing_hours": array_schema(TEXT),
    }),
    "permissions": permissions("read"),
}


def get_team_members(inputs, project):
    try:
        validate(instance=inputs, schema=get_team_members_tool["input_schema"])
    except SchemaValidationError as error:
        return github_issues_error("invalid_input", error.message)

    if inputs["project_id"] != project.get("project_id"):
        return github_issues_error(
            "permission_denied",
            "The requested project is not the active project.",
        )

    saved_members = project.get("members", [])
    if not isinstance(saved_members, list):
        return github_issues_error(
            "invalid_project_data", "Project members must be a list."
        )

    members = []
    missing_hours = []

    for member in saved_members:
        if not isinstance(member, dict):
            return github_issues_error(
                "invalid_project_data", "Each project member must be an object."
            )

        login = member.get("login")
        hours = member.get("hours")
        members.append({"login": login, "hours": hours})

        if hours is None:
            missing_hours.append(login)

    result = success({"members": members, "missing_hours": missing_hours})

    try:
        validate(instance=result, schema=get_team_members_tool["output_schema"])
    except SchemaValidationError as error:
        return github_issues_error("invalid_project_data", error.message)

    return result


# כלי 3 – שיבוץ משימות לפי זמינות
estimate_workload_tool = {
    "name": "estimate_workload",
    "description": (
        "Propose task assignments based on team availability. "
        "Report utilization and tasks that could not be assigned."
    ),
    "input_schema": validate_project_inputs_tool["input_schema"],
    "output_schema": build_output_schema({
        "assignments": array_schema(object_schema({
            "task_id": TEXT,
            "title": TEXT,
            "hours": HOURS,
            "assignee": NULLABLE_TEXT,
        })),
        "team": array_schema(object_schema({
            "login": TEXT,
            "available_hours": HOURS,
            "assigned_hours": HOURS,
            "remaining_hours": HOURS,
            "utilization": {"type": "number", "minimum": 0, "maximum": 100},
        })),
        "unassigned_hours": HOURS,
    }),
    "permissions": permissions("compute-only"),
}


def estimate_workload(inputs):
    validation = validate_project_inputs(inputs)
    if validation["status"] == "error":
        return validation

    team = inputs["team"]
    tasks = inputs["tasks"]

    task_ids = [task["task_id"] for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        return github_issues_error("invalid_input", "Task IDs must be unique.")

    available = {
        member["github_username"]: Decimal(str(member["available_hours"]))
        for member in team
    }
    task_hours = {
        task["task_id"]: Decimal(str(task["estimated_hours"]))
        for task in tasks
    }

    if any(not hours.is_finite() for hours in available.values()) or any(
        not hours.is_finite() for hours in task_hours.values()
    ):
        return github_issues_error("invalid_input", "Hours must be finite numbers.")

    assigned = dict.fromkeys(available, Decimal("0"))
    assignees = {}
    unassigned_hours = Decimal("0")

    sorted_tasks = sorted(
        tasks,
        key=lambda task: task_hours[task["task_id"]],
        reverse=True,
    )

    for task in sorted_tasks:
        task_id = task["task_id"]
        hours = task_hours[task_id]
        candidates = [
            login
            for login in available
            if available[login] - assigned[login] >= hours
        ]

        assignee = min(
            candidates,
            key=lambda login: (assigned[login] + hours) / available[login],
            default=None,
        )
        assignees[task_id] = assignee

        if assignee is None:
            unassigned_hours += hours
        else:
            assigned[assignee] += hours

    assignments = [
        {
            "task_id": task["task_id"],
            "title": task["title"],
            "hours": float(task_hours[task["task_id"]]),
            "assignee": assignees[task["task_id"]],
        }
        for task in tasks
    ]

    team_summary = []
    for login, hours in available.items():
        used = assigned[login]
        utilization = round(float(used / hours * 100), 2) if hours else 0
        team_summary.append({
            "login": login,
            "available_hours": float(hours),
            "assigned_hours": float(used),
            "remaining_hours": float(hours - used),
            "utilization": utilization,
        })

    result = success({
        "assignments": assignments,
        "team": team_summary,
        "unassigned_hours": float(unassigned_hours),
    })

    try:
        validate(instance=result, schema=estimate_workload_tool["output_schema"])
    except SchemaValidationError as error:
        return github_issues_error("invalid_output", error.message)

    return result
