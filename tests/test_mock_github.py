"""

בדיקות אינטגרציה לכלי הקריאה והכתיבה במאגר מדומה משותף

"""

from src.mock_github import MockGitHubClient
from src.read_tools import get_github_issues
from src.write_tools import create_github_issue, update_github_issue


REPO = {"repo_owner": "test-owner", "repo_name": "demo"}
ALLOWED_REPO = ("test-owner", "demo")


def create_task(client, **extra):
    inputs = {**REPO, "title": "Build dashboard", "idempotency_key": "task-001"}
    inputs.update(extra)
    result = create_github_issue(inputs, client, approved=True)
    assert result["status"] == "ok"
    return result["data"]["issue_id"]


def read_tasks(client, **extra):
    result = get_github_issues({**REPO, **extra}, client, ALLOWED_REPO)
    assert result["status"] == "ok"
    return result["data"]["issues"]


# משימה חדשה מופיעה בתוצאות הקריאה
def test_create_then_read():
    client = MockGitHubClient()
    number = create_task(client, assignee="dev-a")
    assert read_tasks(client) == [
        {"id": number, "title": "Build dashboard", "assignees": ["dev-a"]}
    ]


# שינוי שיוך משתקף בקריאה הבאה
def test_update_then_read():
    client = MockGitHubClient()
    number = create_task(client, assignee="dev-a")
    result = update_github_issue(
        {**REPO, "issue_number": number, "assignee": "dev-b"},
        client, approved=True,
    )
    assert result["status"] == "ok"
    assert read_tasks(client)[0]["assignees"] == ["dev-b"]


def test_empty_repository():
    assert read_tasks(MockGitHubClient()) == []


def test_unassigned_issue():
    client = MockGitHubClient()
    create_task(client)
    assert read_tasks(client)[0]["assignees"] == []


def test_repository_isolation():
    client = MockGitHubClient()
    create_task(client, repo_name="other")
    assert read_tasks(client) == []


def test_read_retry():
    client = MockGitHubClient(fail_once=True)
    create_task(client)
    assert len(read_tasks(client)) == 1
    assert client.calls == 2


def test_idempotent_creation():
    client = MockGitHubClient()
    assert create_task(client) == create_task(client)
    assert len(read_tasks(client)) == 1


def test_closed_filter():
    client = MockGitHubClient()
    create_task(client)
    assert read_tasks(client, state="closed") == []
    assert len(read_tasks(client, state="all")) == 1
