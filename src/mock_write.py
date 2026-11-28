"""
קובץ זה מדמה פעולות כתיבה מול
 GitHub API

מאפשר יצירת משימות, עדכון שיוך משימות
מניעת כפילויות והדמיית כשלים

מטרתו לאפשר בדיקות ללא חיבור ל-גיטהב
ללא טוקן וללא שינוי נתונים אמיתיים

"""


class MockGitHubError(Exception):
    def __init__(self, error_type, message):
        super().__init__(message)
        self.error_type = error_type


class MockGitHubWriteClient:

    def __init__(self):
        self.issues = {}
        self.idempotency_keys = {}
        self.next_issue_number = 1
        self.failure_mode = None

    # הגדרת תקלה לצורך בדיקות
    def set_failure(self, failure_mode):
        self.failure_mode = failure_mode

    # הדמיית כשלים בתקשורת מול GitHub
    def _check_failure(self):
        errors = {
            "not_found": "Repository or issue not found.",
            "permission_denied": "Permission denied.",
            "timeout": "GitHub request timed out."
        }

        if self.failure_mode in errors:
            raise MockGitHubError(
                self.failure_mode,
                errors[self.failure_mode]
            )

    # יצירת משימה חדשה
    def create_issue(self, repo_owner, repo_name,
                     title, idempotency_key,
                     body="", assignee=None):

        self._check_failure()

        key = (repo_owner, repo_name, idempotency_key)

        # מניעת יצירת משימה כפולה
        if key in self.idempotency_keys:
            issue_key = self.idempotency_keys[key]
            return self.issues[issue_key].copy()

        issue_number = self.next_issue_number
        self.next_issue_number += 1

        issue = {
            "issue_id": issue_number,
            "title": title,
            "body": body,
            "assignee": assignee,
            "html_url": (
                f"https://github.com/{repo_owner}/"
                f"{repo_name}/issues/{issue_number}"
            )
        }

        issue_key = (repo_owner, repo_name, issue_number)

        self.issues[issue_key] = issue
        self.idempotency_keys[key] = issue_key

        return issue.copy()

    # עדכון שיוך של משימה קיימת
    def update_issue(self, repo_owner, repo_name,
                     issue_number, assignee):

        self._check_failure()

        issue_key = (repo_owner, repo_name, issue_number)

        if issue_key not in self.issues:
            raise MockGitHubError(
                "not_found",
                "Issue not found."
            )

        self.issues[issue_key]["assignee"] = assignee

        return {
            "issue_number": issue_number,
            "assignee": assignee,
            "updated": True
        }