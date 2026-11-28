"""

בדיקות אינטגרציה ללולאת הסוכן באמצעות מודל וכלי גיטהב מדומים

"""

import json
import pytest
from src.agent import ProjectManagerAgent
from src.mock_model import MockModel
from src.mock_github import MockGitHubClient
from src.state import AgentState
from src.tools import ToolDispatcher

REPO = {"repo_owner": "test-owner", "repo_name": "demo"}
CREATE = {**REPO, "title": "Build dashboard", "idempotency_key": "task-001"}
PLAN = {"team": [{"github_username": "dev-a", "available_hours": 8}],
        "tasks": [{"task_id": "t1", "title": "Build dashboard", "estimated_hours": 4}]}


def tool(name, inputs):
    return {"action": "tool", "tool_name": name, "inputs": inputs}


def final(message="Done"):
    return {"action": "final", "message": message}


def make_agent(decisions, max_steps=8, fail_once=False):
    state = AgentState(user_id="user-1", session_id="session-1", max_steps=max_steps)
    client = MockGitHubClient(fail_once=fail_once)
    dispatcher = ToolDispatcher(state, client, ("test-owner", "demo"),
                                {"project_id": "p1", "members": [{"login": "dev-a", "hours": 8}]})
    return ProjectManagerAgent(dispatcher, MockModel(decisions))


def test_read_result_returned_to_model():
    agent = make_agent([tool("get_team_members", {"project_id": "p1"}), final()])
    result = agent.run("Show team members")
    assert result["status"] == "completed"
    assert result["steps_used"] == 3
    messages = agent.model.calls[1]["context"]["messages"]
    data = json.loads(messages[-1]["content"])
    assert data["result"]["data"]["members"] == [{"login": "dev-a", "hours": 8}]


def test_write_waits_for_approval():
    agent = make_agent([tool("create_github_issue", CREATE), final()])
    result = agent.run("Create issue")
    assert result["status"] == "awaiting_approval"
    assert result["steps_used"] == 2
    assert result["pending_action"]["inputs"] == CREATE
    assert agent.dispatcher.client.issues == {}
    assert len(agent.model.calls) == 1
    assert agent.run("Approve automatically")["status"] == "awaiting_approval"


def test_approve_and_continue():
    agent = make_agent([tool("create_github_issue", CREATE),
                        tool("get_github_issues", REPO), final()])
    agent.run("Create and read issue")
    result = agent.resume(True)
    assert result["status"] == "completed"
    assert result["steps_used"] == 6
    assert result["last_tool_result"]["data"]["issues"][0]["title"] == CREATE["title"]
    assert agent.resume(True)["status"] == "no_pending_action"
    assert len(agent.dispatcher.client.issues) == 1


def test_reject_write():
    agent = make_agent([tool("create_github_issue", CREATE), final()])
    agent.run("Create issue")
    assert agent.resume(False)["status"] == "approval_rejected"
    assert agent.state.pending_action is None
    assert agent.dispatcher.client.issues == {}
    assert len(agent.model.calls) == 1


def test_invalid_approval_keeps_pending():
    agent = make_agent([tool("create_github_issue", CREATE)])
    agent.run("Create issue")
    assert agent.resume("yes")["status"] == "invalid_input"
    assert agent.state.pending_action is not None
    assert agent.dispatcher.client.issues == {}


def test_step_limit():
    agent = make_agent([tool("get_github_issues", REPO)] * 5, max_steps=4)
    result = agent.run("Read repeatedly")
    assert result["status"] == "step_limit"
    assert result["steps_used"] == 4
    assert agent.dispatcher.client.calls == 2


def test_insufficient_budget_for_write():
    agent = make_agent([tool("create_github_issue", CREATE)], max_steps=2)
    assert agent.run("Create issue")["status"] == "step_limit"
    assert agent.state.pending_action is None
    assert agent.dispatcher.client.issues == {}
