"""

בדיקות לכלים 1–3 וללקוח הקריאה המדומה

"""

import pytest
from jsonschema import validate
from src.mock_read import DemoGitHubReadClient
from src.read_tools import (
    get_github_issues, get_github_issues_tool,
    get_team_members, get_team_members_tool,
    estimate_workload, estimate_workload_tool,
)

REPO = ("owner", "DevTeam-AI")


def read_inputs(**changes):
    return {"repo_owner": REPO[0], "repo_name": REPO[1], **changes}


def project():
    return {"project_id": "p1", "members": [
        {"login": "dev-a", "hours": 10}, {"login": "dev-b", "hours": 8}
    ]}


def workload():
    return {"team": [
        {"github_username": "dev-a", "available_hours": 10},
        {"github_username": "dev-b", "available_hours": 8},
    ], "tasks": [
        {"task_id": "1", "title": "Login", "estimated_hours": 4},
        {"task_id": "2", "title": "Database", "estimated_hours": 6},
        {"task_id": "3", "title": "Tests", "estimated_hours": 3},
    ]}


def assert_error(result, error_type):
    assert result["status"] == "error"
    assert result["data"] is None
    assert result["error"]["type"] == error_type


# כלי 1 – קריאת משימות והרשאות

def test_read_success():
    result = get_github_issues(read_inputs(), DemoGitHubReadClient(), REPO)
    validate(result, get_github_issues_tool["output_schema"])
    assert result["status"] == "ok"
    assert result["data"]["issues"][0]["id"] == 12


def test_read_closed():
    result = get_github_issues(read_inputs(state="closed"), DemoGitHubReadClient(), REPO)
    assert result["data"]["issues"] == []


def test_read_invalid_input():
    client = DemoGitHubReadClient()
    assert_error(get_github_issues(read_inputs(state="bad"), client, REPO), "invalid_input")
    assert client.calls == 0


def test_read_forbidden_repository():
    client = DemoGitHubReadClient()
    assert_error(get_github_issues(read_inputs(repo_name="other"), client, REPO), "permission_denied")
    assert client.calls == 0


def test_read_recovers_from_timeout():
    client = DemoGitHubReadClient(fail_once=True)
    assert get_github_issues(read_inputs(), client, REPO)["status"] == "ok"
    assert client.calls == 2


def test_read_persistent_timeout():
    class FailingClient:
        calls = 0
        def list_issues(self, **kwargs):
            self.calls += 1
            raise TimeoutError("Simulated timeout")
    client = FailingClient()
    result = get_github_issues(read_inputs(), client, REPO)
    assert_error(result, "transient_failure")
    assert result["error"]["retryable"] is True
    assert client.calls == 3


def test_read_invalid_output():
    class BadClient:
        def list_issues(self, **kwargs):
            return [{"id": -1}]
    assert_error(get_github_issues(read_inputs(), BadClient(), REPO), "invalid_output")


# כלי 2 – חברי צוות וזמינות

def test_team_success():
    result = get_team_members({"project_id": "p1"}, project())
    validate(result, get_team_members_tool["output_schema"])
    assert result["data"]["members"] == project()["members"]
    assert result["data"]["missing_hours"] == []


def test_team_missing_hours():
    data = project()
    data["members"][0].pop("hours")
    result = get_team_members({"project_id": "p1"}, data)
    assert result["data"]["missing_hours"] == ["dev-a"]


def test_team_forbidden_project():
    assert_error(get_team_members({"project_id": "other"}, project()), "permission_denied")


def test_team_invalid_input():
    assert_error(get_team_members({"project_id": " "}, project()), "invalid_input")


def test_team_invalid_data():
    data = project()
    data["members"][0]["hours"] = -1
    assert_error(get_team_members({"project_id": "p1"}, data), "invalid_project_data")


# כלי 3 – שיבוץ ובדיקת החיבור לכלי 4

def test_workload_success():
    result = estimate_workload(workload())
    validate(result, estimate_workload_tool["output_schema"])
    assert result["status"] == "ok"
    data = result["data"]
    assert [a["assignee"] for a in data["assignments"]] == ["dev-b", "dev-a", "dev-b"]
    assert sum(m["assigned_hours"] for m in data["team"]) == 13
    assert sum(m["remaining_hours"] for m in data["team"]) == 5
    assert data["unassigned_hours"] == 0


def test_workload_insufficient_capacity():
    data = workload()
    data["tasks"][1]["estimated_hours"] = 20
    result = estimate_workload(data)
    assert result["data"]["assignments"][1]["assignee"] is None
    assert result["data"]["unassigned_hours"] == 20


def test_workload_duplicate_members():
    data = workload()
    data["team"][1]["github_username"] = "DEV-A"
    assert_error(estimate_workload(data), "duplicate_member")


def test_workload_duplicate_tasks():
    data = workload()
    data["tasks"][1]["task_id"] = "1"
    assert_error(estimate_workload(data), "invalid_input")


def test_workload_negative_hours():
    data = workload()
    data["team"][0]["available_hours"] = -1
    assert_error(estimate_workload(data), "invalid_input")


def test_workload_zero_availability():
    data = workload()
    for member in data["team"]:
        member["available_hours"] = 0
    result = estimate_workload(data)
    assert result["data"]["unassigned_hours"] == 13
    assert all(m["utilization"] == 0 for m in result["data"]["team"])
