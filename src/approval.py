
"""

קובץ זה אחראי על חיבור מנגנון אישור המשתמש
לכלי הכתיבה של הסוכן

המנגנון כולל:
- שמירת פעולה הממתינה לאישור המשתמש
- טיפול באישור או בדחיית הפעולה
- בדיקת התאמה בין הפעולה שאושרה לפעולה המבוקשת
- מניעת שימוש חוזר באותו אישור
- חסימת פעולות כתיבה שלא קיבלו אישור

כלי הכתיבה המחייבים אישור:
- כלי 5
- create_github_issue
- כלי 6
- update_github_issue

קובץ זה משמש שכבת חיבור בין ניהול מצב הסוכן
(state.py) 
לבין כלי הכתיבה 
(write_tools.py)
ולולאת הסוכן

"""

from copy import deepcopy

from src.state import AgentState
from src.write_tools import (
    create_github_issue,
    update_github_issue
)


# רשימת כלי הכתיבה המחייבים אישור משתמש
WRITE_TOOLS = {
    "create_github_issue": create_github_issue,
    "update_github_issue": update_github_issue
}


# יצירת תשובת שגיאה במבנה אחיד
def approval_error(error_type, message):
    return {
        "status": "error",
        "data": None,
        "error": {
            "type": error_type,
            "message": message,
            "retryable": False
        }
    }


# שמירת פעולה שממתינה לאישור המשתמש
def request_write_approval(state: AgentState, tool_name, inputs):

    if tool_name not in WRITE_TOOLS:
        return approval_error(
            "invalid_tool",
            "Unknown write tool."
        )

    if state.pending_action is not None:
        return approval_error(
            "approval_pending",
            "Another action is waiting for approval."
        )

    state.request_approval(tool_name, inputs)

    return {
        "status": "ok",
        "data": deepcopy(state.pending_action),
        "error": None
    }


# טיפול בהחלטת המשתמש
def handle_user_approval(state: AgentState, approved):

    if state.pending_action is None:
        return approval_error(
            "no_pending_action",
            "No action is waiting for approval."
        )

    if approved is True:
        state.approve_action()

    elif approved is False:
        state.reject_action()

    else:
        return approval_error(
            "invalid_input",
            "Approval must be True or False."
        )

    return {
        "status": "ok",
        "data": {"approved": approved},
        "error": None
    }


# הפעלת כלי כתיבה רק לאחר אימות האישור
def execute_approved_write(
    state: AgentState, tool_name, inputs, client
):

    if tool_name not in WRITE_TOOLS:
        return approval_error(
            "invalid_tool",
            "Unknown write tool."
        )

    inputs = deepcopy(inputs)

    # בדיקת התאמה בין הפעולה המבוקשת לפעולה שאושרה
    if not state.consume_approval(tool_name, inputs):
        return approval_error(
            "approval_required",
            "Matching human approval is required."
        )

    # הפעלת הכלי לאחר אימות האישור
    return WRITE_TOOLS[tool_name](
        inputs,
        client,
        approved=True
    )
