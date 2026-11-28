"""

לקוח מדומה לקריאת משימות, ללא חיבור ל-גיטהב

"""


class DemoGitHubReadClient:
    def __init__(self, fail_once=False):
        self.fail_once = fail_once
        self.calls = 0

    def list_issues(self, *, repo_owner, repo_name, state, timeout):
        self.calls += 1

        if self.fail_once and self.calls == 1:
            raise TimeoutError("Simulated timeout")

        if state == "closed":
            return []

        return [{
            "id": 12,
            "title": "Build a dashboard",
            "assignees": ["dev-a"],
        }]
