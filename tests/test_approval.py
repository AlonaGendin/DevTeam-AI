
"""

קובץ זה מכיל בדיקות אוטומטיות למנגנון אישור המשתמש

מטרת הבדיקות היא לוודא את החיבור בין ניהול מצב
הסוכן לבין כלי הכתיבה

הבדיקות כוללות:
- ביצוע פעולות לאחר אישור המשתמש
- חסימת פעולות ללא אישור או לאחר דחייה
- מניעת שימוש חוזר באישור
- מניעת שינוי פרמטרים לאחר אישור
- בידוד אישורים בין משתמשים ושיחות
- התמודדות עם כשלים בפעולות כתיבה

כל הבדיקות מתבצעות באמצעות 
Mock
 ללא שינוי נתונים בגיטהב האמיתי
"""

from src.state import AgentState
from src.mock_write import MockGitHubWriteClient

from src.approval import (
    request_write_approval,
    handle_user_approval,
    execute_approved_write
)


# יצירת מצב סוכן לצורך הבדיקות
def sample_state():
    return AgentState(
        user_id="ortal",
        session_id="session-1"
    )


# יצירת נתוני בדיקה
def sample_inputs():
    return {
        "repo_owner": "test-owner",
        "repo_name": "DevTeam-AI",
        "title": "Build login page",
        "body": "Create the login interface",
        "assignee": "ortal",
        "idempotency_key": "task-001"
    }


# פונקציית עזר לבקשת אישור וקבלתו
def approve_write(state, tool_name, inputs):
    request = request_write_approval(
        state, tool_name, inputs
    )
    assert request["status"] == "ok"

    result = handle_user_approval(state, True)
    assert result["status"] == "ok"


# בדיקת יצירת משימה לאחר אישור
def test_approved_create():
    state = sample_state()
    client = MockGitHubWriteClient()
    inputs = sample_inputs()

    approve_write(
        state, "create_github_issue", inputs
    )

    result = execute_approved_write(
        state, "create_github_issue", inputs, client
    )

    assert result["status"] == "ok"
    assert len(client.issues) == 1
    assert state.approved_action is None


# בדיקת חסימת פעולה ללא אישור
def test_write_without_approval():
    state = sample_state()
    client = MockGitHubWriteClient()

    result = execute_approved_write(
        state, "create_github_issue",
        sample_inputs(), client
    )

    assert result["error"]["type"] == "approval_required"
    assert len(client.issues) == 0


# בדיקת חסימת פעולה הממתינה לאישור
def test_write_while_pending():
    state = sample_state()
    client = MockGitHubWriteClient()
    inputs = sample_inputs()

    request_write_approval(
        state, "create_github_issue", inputs
    )

    result = execute_approved_write(
        state, "create_github_issue", inputs, client
    )

    assert result["error"]["type"] == "approval_required"
    assert len(client.issues) == 0


# בדיקת חסימת פעולה לאחר דחייה
def test_rejected_write():
    state = sample_state()
    client = MockGitHubWriteClient()
    inputs = sample_inputs()

    request_write_approval(
        state, "create_github_issue", inputs
    )

    handle_user_approval(state, False)

    result = execute_approved_write(
        state, "create_github_issue", inputs, client
    )

    assert result["error"]["type"] == "approval_required"
    assert state.pending_action is None
    assert state.approved_action is None
    assert len(client.issues) == 0


# בדיקת מניעת שימוש חוזר באישור
def test_approval_reuse():
    state = sample_state()
    client = MockGitHubWriteClient()
    inputs = sample_inputs()

    approve_write(
        state, "create_github_issue", inputs
    )

    first = execute_approved_write(
        state, "create_github_issue", inputs, client
    )

    second = execute_approved_write(
        state, "create_github_issue", inputs, client
    )

    assert first["status"] == "ok"
    assert second["error"]["type"] == "approval_required"
    assert len(client.issues) == 1


# בדיקת שינוי פרמטרים לאחר אישור
def test_modified_inputs():
    state = sample_state()
    client = MockGitHubWriteClient()
    inputs = sample_inputs()

    approve_write(
        state, "create_github_issue", inputs
    )

    inputs["assignee"] = "alona"

    result = execute_approved_write(
        state, "create_github_issue", inputs, client
    )

    assert result["error"]["type"] == "approval_required"
    assert len(client.issues) == 0


# בדיקת בקשת אישור לכלי לא מוכר
def test_unknown_tool():
    state = sample_state()

    result = request_write_approval(
        state, "merge_pull_request", {}
    )

    assert result["error"]["type"] == "invalid_tool"
    assert state.pending_action is None


# בדיקת מניעת דריסת פעולה הממתינה לאישור
def test_pending_action_override():
    state = sample_state()
    inputs = sample_inputs()

    request_write_approval(
        state, "create_github_issue", inputs
    )

    new_inputs = sample_inputs()
    new_inputs["title"] = "Different task"

    result = request_write_approval(
        state, "create_github_issue", new_inputs
    )

    assert result["error"]["type"] == "approval_pending"
    assert state.pending_action["inputs"] == inputs


# בדיקת אישור כאשר אין פעולה ממתינה
def test_no_pending_action():
    state = sample_state()

    result = handle_user_approval(state, True)

    assert result["error"]["type"] == "no_pending_action"


# בדיקת החלטת משתמש לא תקינה
def test_invalid_approval():
    state = sample_state()

    request_write_approval(
        state, "create_github_issue", sample_inputs()
    )

    result = handle_user_approval(state, "yes")

    assert result["error"]["type"] == "invalid_input"
    assert state.pending_action is not None
    assert state.approved_action is None


# בדיקת בידוד אישורים בין משתמשים
def test_user_isolation():
    state1 = sample_state()

    state2 = AgentState(
        user_id="alona",
        session_id="session-2"
    )

    client = MockGitHubWriteClient()
    inputs = sample_inputs()

    approve_write(
        state1, "create_github_issue", inputs
    )

    result = execute_approved_write(
        state2, "create_github_issue", inputs, client
    )

    assert result["error"]["type"] == "approval_required"
    assert len(client.issues) == 0


# בדיקת בידוד אישורים בין שיחות של אותו משתמש
def test_session_isolation():
    state1 = sample_state()

    state2 = AgentState(
        user_id="ortal",
        session_id="session-2"
    )

    client = MockGitHubWriteClient()
    inputs = sample_inputs()

    approve_write(
        state1, "create_github_issue", inputs
    )

    result = execute_approved_write(
        state2, "create_github_issue", inputs, client
    )

    assert result["error"]["type"] == "approval_required"
    assert len(client.issues) == 0


# בדיקת עדכון משימה עם אישור נפרד
def test_approved_update():
    state = sample_state()
    client = MockGitHubWriteClient()
    inputs = sample_inputs()

    approve_write(
        state, "create_github_issue", inputs
    )

    created = execute_approved_write(
        state, "create_github_issue", inputs, client
    )

    assert created["status"] == "ok"

    update_inputs = {
        "repo_owner": "test-owner",
        "repo_name": "DevTeam-AI",
        "issue_number": created["data"]["issue_id"],
        "assignee": "alona"
    }

    # חסימת עדכון לפני קבלת אישור חדש
    blocked = execute_approved_write(
        state, "update_github_issue",
        update_inputs, client
    )

    assert blocked["error"]["type"] == "approval_required"
    assert next(iter(client.issues.values()))["assignee"] == "ortal"

    approve_write(
        state, "update_github_issue", update_inputs
    )

    result = execute_approved_write(
        state, "update_github_issue",
        update_inputs, client
    )

    assert result["status"] == "ok"
    assert result["data"]["updated"] is True
    assert next(iter(client.issues.values()))["assignee"] == "alona"


# בדיקת מניעת העברת אישור בין כלים שונים
def test_approval_tool_mismatch():
    state = sample_state()
    client = MockGitHubWriteClient()
    inputs = sample_inputs()

    approve_write(
        state, "create_github_issue", inputs
    )

    result = execute_approved_write(
        state, "update_github_issue", inputs, client
    )

    assert result["error"]["type"] == "approval_required"
    assert len(client.issues) == 0


# בדיקת תקלה לאחר אישור ומניעת ניסיון חוזר
def test_approved_write_failure():
    state = sample_state()
    client = MockGitHubWriteClient()
    inputs = sample_inputs()

    client.set_failure("timeout")

    approve_write(
        state, "create_github_issue", inputs
    )

    result = execute_approved_write(
        state, "create_github_issue", inputs, client
    )

    assert result["error"]["type"] == "timeout"
    assert result["error"]["retryable"] is False
    assert state.approved_action is None
    assert len(client.issues) == 0

    client.set_failure(None)

    retry = execute_approved_write(
        state, "create_github_issue", inputs, client
    )

    assert retry["error"]["type"] == "approval_required"
    assert len(client.issues) == 0
