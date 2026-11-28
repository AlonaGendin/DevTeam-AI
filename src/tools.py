"""

מנגנון מרכזי להפעלת הכלים ולניהול אישור פעולות כתיבה

"""

from copy import deepcopy
from jsonschema import validate, ValidationError

from src.read_tools import (
    get_github_issues, get_github_issues_tool,
    get_team_members, get_team_members_tool,
    estimate_workload, estimate_workload_tool,
)
from src.write_tools import (
    validate_project_inputs, validate_project_inputs_tool,
    create_github_issue_tool, update_github_issue_tool,
)
from src.approval import (
    request_write_approval, handle_user_approval, execute_approved_write,
)


# רשימת הכלים המורשים להפעלה על ידי הסוכן
TOOL_CONTRACTS = {
    tool["name"]: tool for tool in (
        get_github_issues_tool, get_team_members_tool,
        estimate_workload_tool, validate_project_inputs_tool,
        create_github_issue_tool, update_github_issue_tool,
    )
}
WRITE_NAMES = {"create_github_issue", "update_github_issue"}
REPO_NAMES = WRITE_NAMES | {"get_github_issues"}


def tool_error(error_type, message):
    return {"status": "error", "data": None, "error": {
        "type": error_type, "message": message, "retryable": False,
    }}


def get_tool_contracts():
    # העתק מונע שינוי חוזים על ידי רכיבים אחרים
    return deepcopy(list(TOOL_CONTRACTS.values()))


class ToolDispatcher:
    def __init__(self, state, client, allowed_repo, project):
        # הנתונים מתקבלים מהיישום ולא מהמודל
        self.state = state
        self.client = client
        self.allowed_repo = tuple(allowed_repo)
        self.project = deepcopy(project)

    def _check_inputs(self, tool_name, inputs):
        if not isinstance(tool_name, str) or tool_name not in TOOL_CONTRACTS:
            return tool_error("invalid_tool", "Tool is not allowed.")
        try:
            validate(instance=inputs, schema=TOOL_CONTRACTS[tool_name]["input_schema"])
        except ValidationError as error:
            return tool_error("invalid_input", error.message)

        # הגבלת הקריאה והכתיבה למאגר שהוגדר מראש
        if tool_name in REPO_NAMES:
            requested = (inputs["repo_owner"], inputs["repo_name"])
            if tuple(x.casefold() for x in requested) != tuple(x.casefold() for x in self.allowed_repo):
                return tool_error("permission_denied", "Repository is not allowed.")
        return None

    def execute(self, tool_name, inputs):
        """הפעלת כלי מתוך לולאת הסוכן. כתיבה רק מבקשת אישור"""
        inputs = deepcopy(inputs)
        error = self._check_inputs(tool_name, inputs)
        if error is not None:
            return error

        if self.state.pending_action is not None or self.state.approved_action is not None:
            return tool_error("approval_pending", "Resolve the pending action first.")

        if tool_name == "get_github_issues":
            return get_github_issues(inputs, self.client, self.allowed_repo)
        if tool_name == "get_team_members":
            return get_team_members(inputs, self.project)
        if tool_name == "estimate_workload":
            return estimate_workload(inputs)
        if tool_name == "validate_project_inputs":
            return validate_project_inputs(inputs)

        # אין אפשרות להעביר אישור כחלק מפרמטרי הכלי
        result = request_write_approval(self.state, tool_name, inputs)
        if result["status"] != "ok":
            return result
        return tool_error("approval_required", "Explicit user approval is required.")

    def resolve_approval(self, approved):
        """המשך פעולה ממתינה בעקבות החלטת משתמש מהממשק בלבד"""
        if type(approved) is not bool:
            return tool_error("invalid_input", "Approval must be a boolean.")
        pending = deepcopy(self.state.pending_action)
        if pending is None:
            return tool_error("no_pending_action", "No action awaits approval.")

        # בדיקה חוזרת לפני ביצוע פעולה שאושרה
        name, inputs = pending["tool_name"], pending["inputs"]
        error = self._check_inputs(name, inputs)
        if error is not None or name not in WRITE_NAMES:
            self.state.reject_action()
            return error or tool_error("invalid_tool", "Not a write tool.")

        result = handle_user_approval(self.state, approved)
        if result["status"] != "ok":
            return result
        if not approved:
            return tool_error("approval_rejected", "The user rejected the action.")
        return execute_approved_write(self.state, name, inputs, self.client)
