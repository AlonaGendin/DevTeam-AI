
"""

בדיקות למנגנון המרכזי להפעלת הכלים

"""

import pytest
from src.state import AgentState
from src.mock_github import MockGitHubClient
from src.tools import ToolDispatcher, get_tool_contracts

REPO = {"repo_owner": "test-owner", "repo_name": "demo"}
CREATE = {**REPO, "title": "Build dashboard", "idempotency_key": "task-001"}
PLAN = {
    "team": [{"github_username": "dev-a", "available_hours": 8}],
    "tasks": [{"task_id": "t1", "title": "Build dashboard", "estimated_hours": 4}],
}


@pytest.fixture
def dispatcher():
    return ToolDispatcher(
        AgentState(user_id="user-1", session_id="session-1"),
        MockGitHubClient(), ("test-owner", "demo"),
        {"project_id": "p1", "members": [{"login": "dev-a", "hours": 8}]},
    )


def error_type(result):
    assert result["status"] == "error"
    return result["error"]["type"]


def test_six_contracts():
    contracts = get_tool_contracts()
    assert len(contracts) == 6
    assert len({item["name"] for item in contracts}) == 6
    contracts[0]["name"] = "changed"
    assert get_tool_contracts()[0]["name"] != "changed"


@pytest.mark.parametrize("name,inputs", [
    ("get_github_issues", REPO),
    ("get_team_members", {"project_id": "p1"}),
    ("estimate_workload", PLAN),
    ("validate_project_inputs", PLAN),
])
def test_read_and_compute(dispatcher, name, inputs):
    assert dispatcher.execute(name, inputs)["status"] == "ok"


def test_unknown_tool(dispatcher):
    assert error_type(dispatcher.execute("merge_pull_request", {})) == "invalid_tool"


def test_invalid_input(dispatcher):
    assert error_type(dispatcher.execute("create_github_issue", {})) == "invalid_input"
    assert dispatcher.state.pending_action is None


def test_unapproved_write(dispatcher):
    assert error_type(dispatcher.execute("create_github_issue", CREATE)) == "approval_required"
    assert dispatcher.client.issues == {}


def test_approved_create_and_read(dispatcher):
    dispatcher.execute("create_github_issue", CREATE)
    assert dispatcher.resolve_approval(True)["status"] == "ok"
    result = dispatcher.execute("get_github_issues", REPO)
    assert result["data"]["issues"][0]["title"] == CREATE["title"]
    assert error_type(dispatcher.resolve_approval(True)) == "no_pending_action"


def test_rejected_write(dispatcher):
    dispatcher.execute("create_github_issue", CREATE)
    assert error_type(dispatcher.resolve_approval(False)) == "approval_rejected"
    assert dispatcher.client.issues == {}
    assert dispatcher.state.pending_action is None


def test_approved_update(dispatcher):
    dispatcher.execute("create_github_issue", CREATE)
    number = dispatcher.resolve_approval(True)["data"]["issue_id"]
    result = dispatcher.execute("update_github_issue", {
        **REPO, "issue_number": number, "assignee": "dev-a",
    })
    assert error_type(result) == "approval_required"
    assert dispatcher.resolve_approval(True)["status"] == "ok"
    assert dispatcher.execute("get_github_issues", REPO)["data"]["issues"][0]["assignees"] == ["dev-a"]


@pytest.mark.parametrize("name,inputs", [
    ("get_github_issues", REPO), ("create_github_issue", CREATE),
    ("update_github_issue", {**REPO, "issue_number": 1, "assignee": "dev-a"}),
])
def test_repository_permission(dispatcher, name, inputs):
    assert error_type(dispatcher.execute(name, {**inputs, "repo_name": "other"})) == "permission_denied"
    assert dispatcher.state.pending_action is None


def test_approval_bypass(dispatcher):
    assert error_type(dispatcher.execute("create_github_issue", {**CREATE, "approved": True})) == "invalid_input"
    assert error_type(dispatcher.execute("resolve_approval", {"approved": True})) == "invalid_tool"
    assert dispatcher.client.issues == {}


def test_pending_cannot_be_replaced(dispatcher):
    dispatcher.execute("create_github_issue", CREATE)
    assert error_type(dispatcher.execute("create_github_issue", {**CREATE, "title": "Other task"})) == "approval_pending"
    assert dispatcher.state.pending_action["inputs"] == CREATE


def test_invalid_approval(dispatcher):
    dispatcher.execute("create_github_issue", CREATE)
    assert error_type(dispatcher.resolve_approval("yes")) == "invalid_input"
    assert dispatcher.client.issues == {}


def test_write_timeout(dispatcher):
    dispatcher.execute("create_github_issue", CREATE)
    dispatcher.client.set_failure("timeout")
    result = dispatcher.resolve_approval(True)
    assert error_type(result) == "timeout"
    assert result["error"]["retryable"] is False
    assert error_type(dispatcher.resolve_approval(True)) == "no_pending_action"
