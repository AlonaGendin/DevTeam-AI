"""
קובץ זה מכיל בדיקות אוטומטיות לניהול מצב הסוכן

הבדיקות בוחנות את תקציב הצעדים
שמירת ההודעות
הפרדה בין שיחות וניהול אישורים אנושיים
תוך מניעת שימוש חוזר באישור או שינוי פעולה שאושרה

"""

from src.state import AgentState


# בדיקת שמירת הודעות
def test_add_message():
    state = AgentState("user1", "session1")

    state.add_message("user", "Create a task")

    assert len(state.messages) == 1
    assert state.messages[0]["role"] == "user"
    assert state.messages[0]["content"] == "Create a task"


# בדיקת הגבלת תקציב הצעדים
def test_step_budget():
    state = AgentState("user1", "session1", max_steps=8)

    for _ in range(8):
        assert state.increment_step() is True

    assert state.steps_used == 8
    assert state.can_continue() is False
    assert state.increment_step() is False
    assert state.steps_used == 8


# בדיקת פעולה הממתינה לאישור
def test_pending_approval():
    state = AgentState("user1", "session1")
    inputs = {"title": "Task A"}

    state.request_approval("create_github_issue", inputs)

    assert state.pending_action is not None
    assert state.approved_action is None
    assert state.consume_approval(
        "create_github_issue", inputs
    ) is False


# בדיקת אישור פעולה
def test_approve_action():
    state = AgentState("user1", "session1")
    inputs = {"title": "Task A"}

    state.request_approval("create_github_issue", inputs)

    assert state.approve_action() is True
    assert state.pending_action is None
    assert state.consume_approval(
        "create_github_issue", inputs
    ) is True


# בדיקת דחיית פעולה
def test_reject_action():
    state = AgentState("user1", "session1")
    inputs = {"title": "Task A"}

    state.request_approval("create_github_issue", inputs)
    state.reject_action()

    assert state.pending_action is None
    assert state.approved_action is None
    assert state.consume_approval(
        "create_github_issue", inputs
    ) is False


# בדיקת מניעת שימוש חוזר באישור
def test_approval_reuse():
    state = AgentState("user1", "session1")
    inputs = {"title": "Task A"}

    state.request_approval("create_github_issue", inputs)
    state.approve_action()

    assert state.consume_approval(
        "create_github_issue", inputs
    ) is True

    assert state.consume_approval(
        "create_github_issue", inputs
    ) is False


# בדיקת שינוי פרמטרים לאחר אישור
def test_modified_action():
    state = AgentState("user1", "session1")
    inputs = {"title": "Task A"}

    state.request_approval("create_github_issue", inputs)
    state.approve_action()

    inputs["title"] = "Task B"

    assert state.consume_approval(
        "create_github_issue", inputs
    ) is False


# בדיקת הפרדה בין שיחות של אותו משתמש
def test_session_isolation():
    first = AgentState("user1", "session1")
    second = AgentState("user1", "session2")

    first.add_message("user", "Private message")
    first.notes["availability"] = 10
    first.increment_step()
    first.request_approval(
        "create_github_issue", {"title": "Task A"}
    )

    assert second.messages == []
    assert second.notes == {}
    assert second.steps_used == 0
    assert second.pending_action is None


# בדיקת הפרדה בין משתמשים
def test_user_isolation():
    first = AgentState("user1", "session1")
    second = AgentState("user2", "session1")

    first.notes["availability"] = 10
    first.request_approval(
        "create_github_issue", {"title": "Task A"}
    )
    first.approve_action()

    assert second.notes == {}
    assert second.approved_action is None

    assert second.consume_approval(
        "create_github_issue", {"title": "Task A"}
    ) is False