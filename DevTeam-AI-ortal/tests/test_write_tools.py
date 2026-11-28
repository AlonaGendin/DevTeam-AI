import pytest
from jsonschema import ValidationError, validate

from src.mock_write import MockGitHubWriteClient
from src.write_tools import (
    create_github_issue,
    create_github_issue_tool,
    estimate_workload,
    get_github_issues,
    get_team_members,
    update_github_issue,
    update_github_issue_tool,
    validate_project_inputs,
    validate_project_inputs_tool,
)


# נתונים משותפים לבדיקות

def sample_inputs():
    return {
        "team": [
            {"github_username": "ortal", "available_hours": 10},
            {"github_username": "alona", "available_hours": 8},
        ],
        "tasks": [
            {"task_id": "1", "title": "Task A", "estimated_hours": 5},
            {"task_id": "2", "title": "Task B", "estimated_hours": 7},
        ],
    }


def sample_issue_inputs():
    return {
        "repo_owner": "test-owner",
        "repo_name": "DevTeam-AI",
        "title": "Build login page",
        "body": "Create the login interface",
        "assignee": "ortal",
        "idempotency_key": "task-001",
    }


def setup_update_issue():
    client = MockGitHubWriteClient()
    result = create_github_issue(sample_issue_inputs(), client, approved=True)
    assert result["status"] == "ok"

    inputs = {
        "repo_owner": "test-owner",
        "repo_name": "DevTeam-AI",
        "issue_number": result["data"]["issue_id"],
        "assignee": "alona",
    }
    return client, inputs


# כלי 1 — קריאת משימות מ-GitHub

READ_REPO = ("test-owner", "DevTeam-AI")
READ_INPUTS = {"repo_owner": READ_REPO[0], "repo_name": READ_REPO[1]}
DEMO_ISSUE = {"id": 12, "title": "Build login page", "assignees": ["ortal"]}


class GitHubReadStub:
    def __init__(self, timeouts_before_success=0):
        self.timeouts_before_success = timeouts_before_success
        self.calls = []

    def list_issues(self, *, repo_owner, repo_name, state, timeout):
        self.calls.append((repo_owner, repo_name, state, timeout))

        if len(self.calls) <= self.timeouts_before_success:
            raise TimeoutError("Simulated timeout")

        return [DEMO_ISSUE]


def test_get_github_issues_valid_input():
    client = GitHubReadStub()

    result = get_github_issues(READ_INPUTS, client, READ_REPO)

    assert result["status"] == "ok"
    assert result["data"]["issues"] == [DEMO_ISSUE]
    assert client.calls == [(*READ_REPO, "open", 3)]


def test_get_github_issues_invalid_input():
    client = GitHubReadStub()
    inputs = {**READ_INPUTS, "state": "pending"}

    result = get_github_issues(inputs, client, READ_REPO)

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_input"
    assert result["error"]["retryable"] is False
    assert client.calls == []


def test_get_github_issues_recovers_after_two_timeouts():
    client = GitHubReadStub(timeouts_before_success=2)

    result = get_github_issues(READ_INPUTS, client, READ_REPO)

    assert result["status"] == "ok"
    assert result["data"]["issues"] == [DEMO_ISSUE]
    assert client.calls == [(*READ_REPO, "open", 3)] * 3


def test_get_github_issues_stops_after_three_timeouts():
    client = GitHubReadStub(timeouts_before_success=3)

    result = get_github_issues(READ_INPUTS, client, READ_REPO)

    assert result["status"] == "error"
    assert result["data"] is None
    assert result["error"]["type"] == "transient_failure"
    assert result["error"]["retryable"] is True
    assert client.calls == [(*READ_REPO, "open", 3)] * 3


# כלי 2 — קריאת חברי הצוות

def test_get_team_members_valid_input():
    members = [{"login": "ortal", "hours": 8}]
    project = {"project_id": "demo", "members": members}

    result = get_team_members({"project_id": "demo"}, project)

    assert result["status"] == "ok"
    assert result["data"] == {"members": members, "missing_hours": []}


def test_get_team_members_missing_project_id():
    project = {"project_id": "demo", "members": []}

    result = get_team_members({}, project)

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_input"
    assert result["error"]["retryable"] is False


def test_get_team_members_distinguishes_missing_hours_from_zero():
    project = {
        "project_id": "demo",
        "members": [
            {"login": "ortal"},
            {"login": "alona", "hours": 0},
        ],
    }

    result = get_team_members({"project_id": "demo"}, project)

    assert result["status"] == "ok"
    assert result["data"]["members"] == [
        {"login": "ortal", "hours": None},
        {"login": "alona", "hours": 0},
    ]
    assert result["data"]["missing_hours"] == ["ortal"]


# כלי 3 — חישוב עומס והצעת שיבוץ

def test_estimate_workload_assigns_tasks_within_capacity():
    result = estimate_workload(sample_inputs())

    assert result["status"] == "ok"
    assert result["data"]["unassigned_hours"] == 0

    assignments = result["data"]["assignments"]
    assert {task["task_id"]: task["assignee"] for task in assignments} == {
        "1": "alona",
        "2": "ortal",
    }

    team = {member["login"]: member for member in result["data"]["team"]}
    assert team["alona"]["remaining_hours"] == 3
    assert team["alona"]["utilization"] == 62.5
    assert team["ortal"]["remaining_hours"] == 3
    assert team["ortal"]["utilization"] == 70


def test_estimate_workload_rejects_negative_task_hours():
    inputs = sample_inputs()
    inputs["tasks"][0]["estimated_hours"] = -5

    result = estimate_workload(inputs)

    assert result["status"] == "error"
    assert result["data"] is None
    assert result["error"]["type"] == "invalid_input"
    assert result["error"]["retryable"] is False


def test_estimate_workload_leaves_task_unassigned_when_it_cannot_fit():
    inputs = sample_inputs()
    inputs["tasks"][0]["estimated_hours"] = 11

    result = estimate_workload(inputs)

    assert result["status"] == "ok"
    assert result["data"]["assignments"][0]["assignee"] is None
    assert result["data"]["unassigned_hours"] == 11


# כלי 4 — אימות נתוני הפרויקט

def test_validate_project_inputs_success():
    result = validate_project_inputs(sample_inputs())

    assert result["status"] == "ok"
    assert result["data"]["valid"] is True
    assert result["data"]["total_available_hours"] == 18
    assert result["data"]["total_required_hours"] == 12
    assert result["data"]["capacity_gap"] == 0
    validate(result, validate_project_inputs_tool["output_schema"])


def test_validate_project_inputs_capacity_gap():
    inputs = sample_inputs()
    inputs["tasks"][0]["estimated_hours"] = 15

    result = validate_project_inputs(inputs)

    assert result["status"] == "ok"
    assert result["data"]["capacity_gap"] == 4


@pytest.mark.parametrize(
    "case, expected_error",
    [
        ("negative_hours", "invalid_input"),
        ("missing_hours", "invalid_input"),
        ("duplicate_member", "duplicate_member"),
    ],
)
def test_validate_project_inputs_rejects_invalid_data(case, expected_error):
    inputs = sample_inputs()

    if case == "negative_hours":
        inputs["team"][0]["available_hours"] = -5
    elif case == "missing_hours":
        del inputs["team"][0]["available_hours"]
    else:
        inputs["team"][1]["github_username"] = "ortal"

    result = validate_project_inputs(inputs)

    assert result["status"] == "error"
    assert result["error"]["type"] == expected_error
    assert result["error"]["retryable"] is False


def test_validate_project_inputs_error_output_schema():
    result = validate_project_inputs({})

    assert result["status"] == "error"
    validate(result, validate_project_inputs_tool["output_schema"])


def test_validate_project_inputs_schema_rejects_missing_output_field():
    result = validate_project_inputs(sample_inputs())
    del result["data"]["capacity_gap"]

    with pytest.raises(ValidationError):
        validate(result, validate_project_inputs_tool["output_schema"])


# כלי 5 — יצירת משימה מדומה

def test_create_issue_success():
    client = MockGitHubWriteClient()

    result = create_github_issue(sample_issue_inputs(), client, approved=True)

    assert result["status"] == "ok"
    assert result["data"]["title"] == "Build login page"
    assert result["data"]["assignee"] == "ortal"
    assert len(client.issues) == 1
    validate(result, create_github_issue_tool["output_schema"])


def test_create_issue_without_approval():
    client = MockGitHubWriteClient()

    result = create_github_issue(sample_issue_inputs(), client)

    assert result["status"] == "error"
    assert result["error"]["type"] == "approval_required"
    assert len(client.issues) == 0


def test_create_issue_approval_bypass():
    client = MockGitHubWriteClient()
    inputs = sample_issue_inputs()
    inputs["approved"] = True

    result = create_github_issue(inputs, client)

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_input"
    assert len(client.issues) == 0


def test_create_issue_invalid_input():
    client = MockGitHubWriteClient()
    inputs = sample_issue_inputs()
    del inputs["title"]

    result = create_github_issue(inputs, client, approved=True)

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_input"
    assert len(client.issues) == 0


def test_create_issue_duplicate():
    client = MockGitHubWriteClient()
    inputs = sample_issue_inputs()

    first = create_github_issue(inputs, client, approved=True)
    second = create_github_issue(inputs, client, approved=True)

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert first["data"]["issue_id"] == second["data"]["issue_id"]
    assert len(client.issues) == 1


@pytest.mark.parametrize(
    "failure_mode", ["not_found", "permission_denied", "timeout"]
)
def test_create_issue_failure(failure_mode):
    client = MockGitHubWriteClient()
    client.set_failure(failure_mode)

    result = create_github_issue(sample_issue_inputs(), client, approved=True)

    assert result["status"] == "error"
    assert result["error"]["type"] == failure_mode
    assert result["error"]["retryable"] is False
    assert len(client.issues) == 0


# כלי 6 — עדכון שיוך משימה מדומה

def test_update_issue_success():
    client, inputs = setup_update_issue()

    result = update_github_issue(inputs, client, approved=True)

    assert result["status"] == "ok"
    assert result["data"]["updated"] is True
    assert result["data"]["assignee"] == "alona"
    validate(result, update_github_issue_tool["output_schema"])

    key = (inputs["repo_owner"], inputs["repo_name"], inputs["issue_number"])
    assert client.issues[key]["assignee"] == "alona"


def test_update_issue_without_approval():
    client, inputs = setup_update_issue()

    result = update_github_issue(inputs, client)

    assert result["status"] == "error"
    assert result["error"]["type"] == "approval_required"
    assert next(iter(client.issues.values()))["assignee"] == "ortal"


def test_update_issue_approval_bypass():
    client, inputs = setup_update_issue()
    inputs["approved"] = True

    result = update_github_issue(inputs, client)

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_input"
    assert next(iter(client.issues.values()))["assignee"] == "ortal"


@pytest.mark.parametrize(
    "issue_number, expected_error",
    [(-1, "invalid_input"), (999, "not_found")],
)
def test_update_issue_invalid_or_missing_issue(issue_number, expected_error):
    client, inputs = setup_update_issue()
    inputs["issue_number"] = issue_number

    result = update_github_issue(inputs, client, approved=True)

    assert result["status"] == "error"
    assert result["error"]["type"] == expected_error
    assert next(iter(client.issues.values()))["assignee"] == "ortal"


@pytest.mark.parametrize("failure_mode", ["permission_denied", "timeout"])
def test_update_issue_failure(failure_mode):
    client, inputs = setup_update_issue()
    client.set_failure(failure_mode)

    result = update_github_issue(inputs, client, approved=True)

    assert result["status"] == "error"
    assert result["error"]["type"] == failure_mode
    assert result["error"]["retryable"] is False
    assert next(iter(client.issues.values()))["assignee"] == "ortal"