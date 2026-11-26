"""
קובץ זה אחראי על ניהול מצב השיחה של הסוכן

כולל זיהוי משתמש ושיחה
ניהול תקציב צעדים
שמירת הודעות וניהול אישורים אנושיים לפעולות כתיבה

"""


from dataclasses import dataclass, field
from copy import deepcopy


@dataclass
class AgentState:

    user_id: str
    session_id: str

    max_steps: int = 8
    steps_used: int = 0

    messages: list = field(default_factory=list)
    notes: dict = field(default_factory=dict)

    pending_action: dict | None = None
    approved_action: dict | None = None

    # הוספת הודעה להיסטוריית השיחה
    def add_message(self, role, content):
        self.messages.append({
            "role": role,
            "content": content
        })

    # בדיקה האם נותרו צעדים זמינים
    def can_continue(self):
        return self.steps_used < self.max_steps

    # עדכון מספר הצעדים שבוצעו
    def increment_step(self):
        if not self.can_continue():
            return False

        self.steps_used += 1
        return True

    # שמירת פעולה הממתינה לאישור אנושי
    def request_approval(self, tool_name, inputs):
        self.approved_action = None
        self.pending_action = {
            "tool_name": tool_name,
            "inputs": deepcopy(inputs)
        }

    # אישור הפעולה הממתינה מצד המשתמש
    def approve_action(self):
        if self.pending_action is None:
            return False

        self.approved_action = self.pending_action
        self.pending_action = None
        return True

    # דחיית הפעולה הממתינה
    def reject_action(self):
        self.pending_action = None
        self.approved_action = None

    # בדיקת התאמה בין הפעולה המבוקשת לפעולה שאושרה
    def consume_approval(self, tool_name, inputs):
        expected = {
            "tool_name": tool_name,
            "inputs": inputs
        }

        if self.approved_action != expected:
            return False

        self.approved_action = None
        return True