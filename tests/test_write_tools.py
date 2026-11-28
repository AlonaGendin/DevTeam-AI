"""
קובץ זה מכיל בדיקות אוטומטיות לכלים 4-6 במערכת

מטרת הבדיקות היא לוודא את תקינות פעולת הכלים
אימות הקלט והפלט, טיפול בשגיאות, אכיפת הרשאות
והתמודדות עם כשלים בתקשורת מול גיטהב

הבדיקות מבוצעות ללא שינוי נתונים ב-גיטהב האמיתי

"""


from src.write_tools import validate_project_inputs
import pytest
from src.write_tools import create_github_issue
from src.mock_write import MockGitHubWriteClient
from src.write_tools import update_github_issue

# יצירת נתוני בדיקה בסיסיים
def sample_inputs():
    return {
        "team": [
            {"github_username": "ortal", "available_hours": 10},
            {"github_username": "alona", "available_hours": 8}
        ],
        "tasks": [
            {"task_id": "1", "title": "Task A", "estimated_hours": 5},
            {"task_id": "2", "title": "Task B", "estimated_hours": 7}
        ]
    }


# בדיקת קלט תקין
def test_valid_inputs():
    result = validate_project_inputs(sample_inputs())

    assert result["status"] == "ok"
    assert result["data"]["valid"] is True
    assert result["data"]["total_available_hours"] == 18
    assert result["data"]["total_required_hours"] == 12
    assert result["data"]["capacity_gap"] == 0


# בדיקת מחסור בשעות
def test_capacity_gap():
    inputs = sample_inputs()
    inputs["tasks"][0]["estimated_hours"] = 15

    result = validate_project_inputs(inputs)

    assert result["status"] == "ok"
    assert result["data"]["capacity_gap"] == 4


# בדיקת שעות שליליות
def test_negative_hours():
    inputs = sample_inputs()
    inputs["team"][0]["available_hours"] = -5

    result = validate_project_inputs(inputs)

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_input"
    assert result["error"]["retryable"] is False


# בדיקת חבר צוות כפול
def test_duplicate_member():
    inputs = sample_inputs()
    inputs["team"][1]["github_username"] = "ortal"

    result = validate_project_inputs(inputs)

    assert result["status"] == "error"
    assert result["error"]["type"] == "duplicate_member"


# בדיקת שדה חובה חסר
def test_missing_field():
    inputs = sample_inputs()
    del inputs["team"][0]["available_hours"]

    result = validate_project_inputs(inputs)

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_input"



    # נתוני בדיקה ליצירת משימה
def sample_issue_inputs():
    return {
        "repo_owner": "test-owner",
        "repo_name": "DevTeam-AI",
        "title": "Build login page",
        "body": "Create the login interface",
        "assignee": "ortal",
        "idempotency_key": "task-001"
    }


# בדיקת יצירת משימה עם אישור אנושי
def test_create_issue_success():
    client = MockGitHubWriteClient()

    result = create_github_issue(
        sample_issue_inputs(), client, approved=True
    )

    assert result["status"] == "ok"
    assert result["data"]["title"] == "Build login page"
    assert result["data"]["assignee"] == "ortal"
    assert len(client.issues) == 1


# בדיקת חסימת פעולה ללא אישור
def test_create_issue_without_approval():
    client = MockGitHubWriteClient()

    result = create_github_issue(
        sample_issue_inputs(), client
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == "approval_required"
    assert len(client.issues) == 0


# בדיקת ניסיון להעביר אישור דרך הקלט
def test_create_issue_approval_bypass():
    client = MockGitHubWriteClient()
    inputs = sample_issue_inputs()
    inputs["approved"] = True

    result = create_github_issue(inputs, client)

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_input"
    assert len(client.issues) == 0


# בדיקת מניעת יצירת משימות כפולות
def test_create_issue_duplicate():
    client = MockGitHubWriteClient()
    inputs = sample_issue_inputs()

    first = create_github_issue(
        inputs, client, approved=True
    )

    second = create_github_issue(
        inputs, client, approved=True
    )

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert first["data"]["issue_id"] == second["data"]["issue_id"]
    assert len(client.issues) == 1


# בדיקת קלט לא תקין
def test_create_issue_invalid_input():
    client = MockGitHubWriteClient()
    inputs = sample_issue_inputs()
    del inputs["title"]

    result = create_github_issue(
        inputs, client, approved=True
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_input"
    assert len(client.issues) == 0


# בדיקת שלושה סוגי כשלים מול GitHub
@pytest.mark.parametrize("failure_mode", [
    "not_found",
    "permission_denied",
    "timeout"
])
def test_create_issue_failure(failure_mode):
    client = MockGitHubWriteClient()
    client.set_failure(failure_mode)

    result = create_github_issue(
        sample_issue_inputs(), client, approved=True
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == failure_mode
    assert result["error"]["retryable"] is False
    assert len(client.issues) == 0


# יצירת משימה מדומה לצורך בדיקות עדכון
def setup_update_issue():
    client = MockGitHubWriteClient()

    result = create_github_issue(
        sample_issue_inputs(), client, approved=True
    )

    assert result["status"] == "ok"

    inputs = {
        "repo_owner": "test-owner",
        "repo_name": "DevTeam-AI",
        "issue_number": result["data"]["issue_id"],
        "assignee": "alona"
    }

    return client, inputs


# בדיקת עדכון משימה עם אישור
def test_update_issue_success():
    client, inputs = setup_update_issue()

    result = update_github_issue(
        inputs, client, approved=True
    )

    assert result["status"] == "ok"
    assert result["data"]["updated"] is True
    assert result["data"]["assignee"] == "alona"

    # בדיקה שהשיוך השתנה בפועל בזיכרון
    key = (
        inputs["repo_owner"],
        inputs["repo_name"],
        inputs["issue_number"]
    )

    assert client.issues[key]["assignee"] == "alona"


# בדיקת חסימת עדכון ללא אישור
def test_update_issue_without_approval():
    client, inputs = setup_update_issue()

    result = update_github_issue(inputs, client)

    assert result["status"] == "error"
    assert result["error"]["type"] == "approval_required"
    assert next(iter(client.issues.values()))["assignee"] == "ortal"


# בדיקת ניסיון עקיפת אישור דרך הקלט
def test_update_issue_approval_bypass():
    client, inputs = setup_update_issue()
    inputs["approved"] = True

    result = update_github_issue(inputs, client)

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_input"
    assert next(iter(client.issues.values()))["assignee"] == "ortal"


# בדיקת מספר משימה לא תקין
def test_update_issue_invalid_input():
    client, inputs = setup_update_issue()
    inputs["issue_number"] = -1

    result = update_github_issue(
        inputs, client, approved=True
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == "invalid_input"


# בדיקת משימה שאינה קיימת
def test_update_issue_not_found():
    client, inputs = setup_update_issue()
    inputs["issue_number"] = 999

    result = update_github_issue(
        inputs, client, approved=True
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == "not_found"


# בדיקת כשלים מול GitHub
@pytest.mark.parametrize("failure_mode", [
    "permission_denied",
    "timeout"
])
def test_update_issue_failure(failure_mode):
    client, inputs = setup_update_issue()
    client.set_failure(failure_mode)

    result = update_github_issue(
        inputs, client, approved=True
    )

    assert result["status"] == "error"
    assert result["error"]["type"] == failure_mode
    assert result["error"]["retryable"] is False
    assert next(iter(client.issues.values()))["assignee"] == "ortal"


from jsonschema import validate, ValidationError

from src.write_tools import (
    validate_project_inputs_tool,
    create_github_issue_tool,
    update_github_issue_tool
)


# בדיקת סכמת פלט של כלי 4
def test_validate_output_schema():
    result = validate_project_inputs(sample_inputs())

    validate(
        result,
        validate_project_inputs_tool["output_schema"]
    )


# בדיקת סכמת פלט של כלי 5
def test_create_output_schema():
    client = MockGitHubWriteClient()

    result = create_github_issue(
        sample_issue_inputs(), client, approved=True
    )

    validate(
        result,
        create_github_issue_tool["output_schema"]
    )


# בדיקת סכמת פלט של כלי 6
def test_update_output_schema():
    client, inputs = setup_update_issue()

    result = update_github_issue(
        inputs, client, approved=True
    )

    validate(
        result,
        update_github_issue_tool["output_schema"]
    )


# בדיקת סכמת פלט במקרה של שגיאה
def test_error_output_schema():
    result = validate_project_inputs({})

    validate(
        result,
        validate_project_inputs_tool["output_schema"]
    )


# בדיקה שהסכמה מזהה פלט לא תקין
def test_invalid_output_schema():
    result = validate_project_inputs(sample_inputs())

    del result["data"]["capacity_gap"]

    with pytest.raises(ValidationError):
        validate(
            result,
            validate_project_inputs_tool["output_schema"]
        )
