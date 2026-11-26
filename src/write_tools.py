"""
קובץ זה מכיל את חוזי הכלים ואת מימוש הכלים הבאים
- validate_project_inputs: בדיקת תקינות נתוני הצוות והמשימות
- create_github_issue: יצירת משימה חדשה ב-גיטהב
- update_github_issue: עדכון שיוך משימה קיימת ב-גיטהב

פעולות כתיבה מחייבות אישור אנושי לפני ביצוען

"""


from jsonschema import validate, ValidationError
from src.mock_write import MockGitHubError

# חוזה כלי 4
validate_project_inputs_tool = {
    "name": "validate_project_inputs",
    "description": "Validate team members, availability hours, and decomposed tasks in deterministic code before estimate_workload. Detects missing availability, duplicate usernames, or capacity gaps. Do not use for calling GitHub API.",
    "input_schema": {
        "type": "object",
        "properties": {
            "team": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "properties": {
                        "github_username": {"type": "string", "minLength": 1, "maxLength": 39},
                        "available_hours": {"type": "number", "minimum": 0, "maximum": 200}
                    },
                    "required": ["github_username", "available_hours"],
                    "additionalProperties": False
                }
            },
            "tasks": {
                "type": "array",
                "minItems": 1,
                "maxItems": 100,
                "items": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "minLength": 1, "maxLength": 20},
                        "title": {"type": "string", "minLength": 1, "maxLength": 200},
                        "estimated_hours": {"type": "number", "exclusiveMinimum": 0, "maximum": 200}
                    },
                    "required": ["task_id", "title", "estimated_hours"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["team", "tasks"],
        "additionalProperties": False
    },
    "output_schema": {
        "status": "ok | error",
        "data": "object (valid, missing_fields, total_available_hours, total_required_hours, capacity_gap)",
        "error": {"type": "string", "message": "string", "retryable": "boolean"}
    },
    "errors": {
        "invalid_input": "Negative hours or malformed input. Do not retry; use ask_user to clarify.",
        "duplicate_member": "Duplicate github_username found in team list. Do not retry; ask user to resolve."
    },
    "permissions": {
        "access": "compute-only",
        "side_effects": "none",
        "requires_human_approval": False,
        "allowed_caller": "agent"
    }
}

# חוזה כלי 5
create_github_issue_tool = {
    "name": "create_github_issue",
    "description": "Create a new issue in a GitHub repository from a decomposed project requirement and optionally assign it to a team member. Write operation that modifies external repository state. Requires explicit human approval before execution.",
    "input_schema": {
        "type": "object",
        "properties": {
            "repo_owner": {"type": "string", "minLength": 1, "maxLength": 50},
            "repo_name": {"type": "string", "minLength": 1, "maxLength": 100},
            "title": {"type": "string", "minLength": 3, "maxLength": 200},
            "body": {"type": "string", "minLength": 0, "maxLength": 2000, "default": ""},
            "assignee": {"type": "string", "minLength": 1, "maxLength": 39},
            "idempotency_key": {"type": "string", "minLength": 8, "maxLength": 64}
        },
        "required": ["repo_owner", "repo_name", "title", "idempotency_key"],
        "additionalProperties": False
    },
    "output_schema": {
        "status": "ok | error",
        "data": "object (issue_id, title, assignee, html_url)",
        "error": {"type": "string", "message": "string", "retryable": "boolean"}
    },
    "errors": {
        "invalid_input": "Missing title or invalid repository parameters. Do not retry; check arguments.",
        "not_found": "Repository not found (404). Do not retry; report to user.",
        "permission_denied": "No write access to repository (403). Do not retry; report to user.",
        "approval_required": "Blocked until explicit user approval is confirmed in state.",
        "timeout": "GitHub did not respond. Do not auto-retry write action to prevent duplicate issues; report to user."
    },
    "permissions": {
        "access": "write",
        "side_effects": "creates a new issue in GitHub",
        "requires_human_approval": True,
        "allowed_caller": "agent (only after human approval)"
    }
}

# חוזה כלי 6
update_github_issue_tool = {
    "name": "update_github_issue",
    "description": "Assign or update the assignee of an existing GitHub repository issue. Write operation that modifies external repository state. Requires explicit human approval before execution. Do not use for creating new issues or deleting issues.",
    "input_schema": {
        "type": "object",
        "properties": {
            "repo_owner": {"type": "string", "minLength": 1, "maxLength": 50},
            "repo_name": {"type": "string", "minLength": 1, "maxLength": 100},
            "issue_number": {"type": "integer", "minimum": 1, "maximum": 100000},
            "assignee": {"type": "string", "minLength": 1, "maxLength": 39}
        },
        "required": ["repo_owner", "repo_name", "issue_number", "assignee"],
        "additionalProperties": False
    },
    "output_schema": {
        "status": "ok | error",
        "data": "object (issue_number, assignee, updated)",
        "error": {"type": "string", "message": "string", "retryable": "boolean"}
    },
    "errors": {
        "invalid_input": "Invalid issue number or username. Do not retry; validate arguments.",
        "not_found": "Issue or repository not found (404). Do not retry; report to user.",
        "permission_denied": "No write access to repository (403). Do not retry; report to user.",
        "approval_required": "Blocked until explicit user approval is confirmed in state.",
        "timeout": "GitHub did not respond. Do not auto-retry write action to prevent duplicates; report to user."
    },
    "permissions": {
        "access": "write",
        "side_effects": "modifies issue assignee in GitHub",
        "requires_human_approval": True,
        "allowed_caller": "agent (only after human approval)"
    }
}


# יצירת סכמת פלט אחידה לכל הכלים
def build_output_schema(data_properties):

    return {
        "type": "object",
        "properties": {
            "status": {
                "enum": ["ok", "error"]
            },
            "data": {
                "type": ["object", "null"],
                "properties": data_properties,
                "required": list(data_properties.keys()),
                "additionalProperties": False
            },
            "error": {
                "type": ["object", "null"],
                "properties": {
                    "type": {"type": "string"},
                    "message": {"type": "string"},
                    "retryable": {"type": "boolean"}
                },
                "required": [
                    "type", "message", "retryable"
                ],
                "additionalProperties": False
            }
        },
        "required": ["status", "data", "error"],
        "additionalProperties": False,
        "if": {
            "properties": {
                "status": {"const": "ok"}
            }
        },
        "then": {
            "properties": {
                "data": {"type": "object"},
                "error": {"type": "null"}
            }
        },
        "else": {
            "properties": {
                "data": {"type": "null"},
                "error": {"type": "object"}
            }
        }
    }


# סכמת פלט לכלי 4
validate_project_inputs_tool["output_schema"] = (
    build_output_schema({
        "valid": {"type": "boolean"},
        "missing_fields": {
            "type": "array",
            "items": {"type": "string"}
        },
        "total_available_hours": {
            "type": "number", "minimum": 0
        },
        "total_required_hours": {
            "type": "number", "minimum": 0
        },
        "capacity_gap": {
            "type": "number", "minimum": 0
        }
    })
)


# סכמת פלט לכלי 5
create_github_issue_tool["output_schema"] = (
    build_output_schema({
        "issue_id": {
            "type": "integer", "minimum": 1
        },
        "title": {"type": "string"},
        "assignee": {"type": ["string", "null"]},
        "html_url": {"type": "string"}
    })
)


# סכמת פלט לכלי 6
update_github_issue_tool["output_schema"] = (
    build_output_schema({
        "issue_number": {
            "type": "integer", "minimum": 1
        },
        "assignee": {"type": "string"},
        "updated": {"type": "boolean"}
    })
)

def validate_project_inputs(inputs):

    # בדיקת תקינות הקלט מול הסכמה
    try:
        validate(
            instance=inputs,
            schema=validate_project_inputs_tool["input_schema"]
        )

    except ValidationError as e:
        return {
            "status": "error",
            "data": None,
            "error": {
                "type": "invalid_input",
                "message": e.message,
                "retryable": False
            }
        }

    team = inputs["team"]
    tasks = inputs["tasks"]

    # בדיקת כפילויות בחברי הצוות
    usernames = [
        member["github_username"].lower()
        for member in team
    ]

    if len(usernames) != len(set(usernames)):
        return {
            "status": "error",
            "data": None,
            "error": {
                "type": "duplicate_member",
                "message": "Duplicate team member found.",
                "retryable": False
            }
        }

    # חישוב סך השעות הזמינות
    total_available = sum(
        member["available_hours"]
        for member in team
    )

    # חישוב סך השעות הנדרשות
    total_required = sum(
        task["estimated_hours"]
        for task in tasks
    )

    # חישוב פער בשעות העבודה
    capacity_gap = max(0, total_required - total_available)

    # החזרת תוצאה מובנית
    return {
        "status": "ok",
        "data": {
            "valid": True,
            "missing_fields": [],
            "total_available_hours": total_available,
            "total_required_hours": total_required,
            "capacity_gap": capacity_gap
        },
        "error": None
    }


def create_github_issue(inputs, client, approved=False):
    """יצירת משימה חדשה לאחר אימות קלט ואישור אנושי."""

    # בדיקת תקינות הקלט מול חוזה הכלי
    try:
        validate(
            instance=inputs,
            schema=create_github_issue_tool["input_schema"]
        )

    except ValidationError as e:
        return {
            "status": "error",
            "data": None,
            "error": {
                "type": "invalid_input",
                "message": e.message,
                "retryable": False
            }
        }

    # חסימת פעולת כתיבה ללא אישור אנושי
    if approved is not True:
        return {
            "status": "error",
            "data": None,
            "error": {
                "type": "approval_required",
                "message": "Human approval is required.",
                "retryable": False
            }
        }

    # יצירת המשימה באמצעות הלקוח המדומה
    try:
        issue = client.create_issue(**inputs)

        return {
            "status": "ok",
            "data": {
                "issue_id": issue["issue_id"],
                "title": issue["title"],
                "assignee": issue["assignee"],
                "html_url": issue["html_url"]
            },
            "error": None
        }

    # טיפול בכשלים ללא ניסיון חוזר אוטומטי
    except MockGitHubError as e:
        return {
            "status": "error",
            "data": None,
            "error": {
                "type": e.error_type,
                "message": str(e),
                "retryable": False
            }
        }


def update_github_issue(inputs, client, approved=False):
    """עדכון שיוך משימה קיימת לאחר אימות קלט ואישור אנושי."""

    # בדיקת תקינות הקלט מול חוזה הכלי
    try:
        validate(
            instance=inputs,
            schema=update_github_issue_tool["input_schema"]
        )

    except ValidationError as e:
        return {
            "status": "error",
            "data": None,
            "error": {
                "type": "invalid_input",
                "message": e.message,
                "retryable": False
            }
        }

    # חסימת פעולת כתיבה ללא אישור אנושי
    if approved is not True:
        return {
            "status": "error",
            "data": None,
            "error": {
                "type": "approval_required",
                "message": "Human approval is required.",
                "retryable": False
            }
        }

    # עדכון שיוך המשימה באמצעות הלקוח המדומה
    try:
        result = client.update_issue(**inputs)

        return {
            "status": "ok",
            "data": {
                "issue_number": result["issue_number"],
                "assignee": result["assignee"],
                "updated": result["updated"]
            },
            "error": None
        }

    # טיפול בכשלים ללא ניסיון חוזר אוטומטי
    except MockGitHubError as e:
        return {
            "status": "error",
            "data": None,
            "error": {
                "type": e.error_type,
                "message": str(e),
                "retryable": False
            }
        }