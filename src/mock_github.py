"""

לקוח GitHub מדומה המאפשר קריאה וכתיבה באותו מאגר משימות

"""

from src.mock_write import MockGitHubWriteClient


class MockGitHubClient(MockGitHubWriteClient):
    def __init__(self, fail_once=False):
        super().__init__()
        self.fail_once = fail_once
        self.calls = 0

    # קריאת המשימות מתוך המאגר המשמש גם לפעולות הכתיבה
    def list_issues(self, *, repo_owner, repo_name, state, timeout):
        self.calls += 1

        # הדמיית כשל זמני בקריאה בלבד
        if self.fail_once and self.calls == 1:
            raise TimeoutError("Simulated timeout")

        if state not in ("open", "closed", "all"):
            raise ValueError("Invalid issue state")

        # המימוש הנוכחי תומך ביצירת משימות פתוחות בלבד
        if state == "closed":
            return []

        result = []
        for (owner, repo, number), issue in self.issues.items():
            if (owner, repo) != (repo_owner, repo_name):
                continue

            # התאמת מבנה הנתונים לחוזה של כלי הקריאה
            assignee = issue["assignee"]
            result.append({
                "id": number,
                "title": issue["title"],
                "assignees": [assignee] if assignee else [],
            })

        return result
