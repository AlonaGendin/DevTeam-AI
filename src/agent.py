"""

לולאת סוכן מנהל פרויקט עם תקציב צעדים ואישור משתמ

"""

import json
from copy import deepcopy

from src.tools import WRITE_NAMES, get_tool_contracts


class ProjectManagerAgent:
    def __init__(self, dispatcher, model):
        self.dispatcher = dispatcher
        self.state = dispatcher.state
        self.model = model
        self.trace = []
        self.active = False
        self.last_tool_result = None

    def _result(self, status, message="", **details):
        return {"status": status, "message": message,
                "steps_used": self.state.steps_used, **deepcopy(details)}

    def _record(self, event, **details):
        self.trace.append({"step": self.state.steps_used,
                           "event": event, **deepcopy(details)})

    # כל קריאת מודל או הפעלת כלי צורכת צעד אחד
    def _take_step(self):
        if self.state.steps_used >= self.state.max_steps:
            return False
        self.state.steps_used += 1
        return True

    def _finish(self, status, message):
        self.active = False
        self.state.add_message("assistant", message)
        self._record("stop", status=status, message=message)
        return self._result(status, message,
                            last_tool_result=self.last_tool_result)

    def _limit(self):
        # אין להשאיר פעולת כתיבה ממתינה כאשר תקציב הצעדים נגמר
        self.state.reject_action()
        return self._finish("step_limit", "Step budget exhausted.")

    def _waiting(self):
        return self._result("awaiting_approval", "User approval required.",
                            pending_action=self.state.pending_action)

    def _context(self):
        # בשלב זה נשלח ההקשר המלא. בהמשך נחבר את מנגנון צמצום ההקשר.
        return deepcopy({
            "messages": self.state.messages,
            "notes": self.state.notes,
            "allowed_repo": list(self.dispatcher.allowed_repo),
            "project_id": self.dispatcher.project.get("project_id"),
            "remaining_steps": self.state.max_steps - self.state.steps_used,
        })

    def _save_tool_result(self, name, result):
        self.last_tool_result = deepcopy(result)
        self.state.add_message("tool", json.dumps(
            {"tool_name": name, "result": result}, ensure_ascii=False))
        self._record("tool_result", tool_name=name, result=result)

    # התחלת בקשה חדשה. תקציב הצעדים מתאפס רק בתחילת בקשה חדשה.
    def run(self, user_message):
        if self.state.pending_action is not None:
            return self._waiting()
        if self.active or self.state.approved_action is not None:
            return self._result("invalid_state", "Resolve the active request first.")
        if not isinstance(user_message, str) or not user_message.strip():
            return self._result("invalid_input", "A nonempty user message is required.")
        self.state.steps_used = 0
        self.trace = []
        self.last_tool_result = None
        self.active = True
        self.state.add_message("user", user_message)
        return self._loop()

    # קבלת החלטת אישור מממשק המשתמש בלבד, ולא מתוך תשובת המודל
    def resume(self, approved):
        if not self.active or self.state.pending_action is None:
            return self._result("no_pending_action", "No action awaits approval.")
        if type(approved) is not bool:
            return self._result("invalid_input", "Approval must be a boolean.")
        pending = deepcopy(self.state.pending_action)
        self._record("human_decision", approved=approved, action=pending)
        if not approved:
            result = self.dispatcher.resolve_approval(False)
            self._save_tool_result(pending["tool_name"], result)
            return self._finish("approval_rejected", "The user rejected the action.")
        if not self._take_step():
            return self._limit()
        self._record("approved_write", action=pending)
        try:
            result = self.dispatcher.resolve_approval(True)
        except Exception:
            self.state.reject_action()
            return self._finish("tool_error", "Write execution failed; verify its outcome before retrying.")
        self._save_tool_result(pending["tool_name"], result)
        if result["status"] != "ok":
            return self._finish("tool_error", "The approved write failed; no automatic retry.")
        return self._loop()

    def _loop(self):
        while self.active:
            if self.state.pending_action is not None:
                return self._waiting()
            if not self._take_step():
                return self._limit()

            # המודל מציע פעולה בלבד. הקוד אחראי על הביצוע וההרשאות.
            try:
                decision = self.model.decide(self._context(), get_tool_contracts())
            except Exception:
                return self._finish("model_error", "Model call failed.")
            self._record("model_decision", decision=decision)
            if not isinstance(decision, dict):
                return self._finish("invalid_decision", "Invalid model decision.")
            action = decision.get("action")

            # החלטות עצירה תקינות: תשובה, בקשת הבהרה או בקשה מחוץ לתחום
            if action in ("final", "clarify", "out_of_scope"):
                message = decision.get("message")
                if set(decision) != {"action", "message"} or not isinstance(message, str) or not message.strip():
                    return self._finish("invalid_decision", "Invalid model message.")
                statuses = {"final": "completed", "clarify": "needs_clarification",
                            "out_of_scope": "out_of_scope"}
                return self._finish(statuses[action], message)

            if (action != "tool" or set(decision) != {"action", "tool_name", "inputs"}
                    or not isinstance(decision.get("tool_name"), str)
                    or not isinstance(decision.get("inputs"), dict)):
                return self._finish("invalid_decision", "Invalid tool decision.")

            name, inputs = decision["tool_name"], decision["inputs"]
            # לכלי כתיבה נדרש צעד לבקשת האישור וצעד נפרד לביצוע לאחר אישור
            needed = 2 if name in WRITE_NAMES else 1
            if self.state.max_steps - self.state.steps_used < needed:
                return self._limit()
            self._take_step()
            self.state.add_message("assistant", json.dumps(decision, ensure_ascii=False))
            self._record("tool_call", tool_name=name, inputs=inputs)
            try:
                result = self.dispatcher.execute(name, inputs)
            except Exception:
                self.state.reject_action()
                return self._finish("tool_error", "Tool execution failed.")
            self._save_tool_result(name, result)

            if result["status"] == "ok":
                continue
            if (result["error"]["type"] == "approval_required"
                    and self.state.pending_action is not None):
                return self._waiting()
            # ניסיונות חוזרים בקריאה מטופלים בתוך הכלי; אין ניסיון חוזר אוטומטי בכתיבה
            return self._finish("tool_error", "Tool returned an error.")
