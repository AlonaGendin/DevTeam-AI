"""

הרצה ידנית של הסוכן עם גמנאי ומאגר גיטהב מדומה בלבד

"""

import json
from pathlib import Path

from dotenv import load_dotenv
from src.agent import ProjectManagerAgent
from src.gemini_model import GeminiModel
from src.mock_github import MockGitHubClient
from src.state import AgentState
from src.tools import ToolDispatcher


def main():
    # טעינת המפתח המקומי בלי להציג אותו או לשמור אותו בתיעוד.
    load_dotenv()
    state = AgentState(user_id="demo-user", session_id="demo-session", max_steps=20)
    client = MockGitHubClient()
    project = {
        "project_id": "p1",
        "members": [{"login": "dev-a", "hours": 8}, {"login": "dev-b", "hours": 2}],
    }
    dispatcher = ToolDispatcher(state, client, ("test-owner", "demo"), project)
    agent = ProjectManagerAgent(dispatcher, GeminiModel())

    # בקשה קבועה כדי שאפשר יהיה להשוות בין הרצות.
    request = (
        "בדוק את המשימות הקיימות ואת זמינות הצוות בפרויקט. "
        "תכנן משימה אחת לפיתוח מסך התחברות בהיקף 4 שעות. "
        "אמת את הנתונים וחשב את חלוקת העבודה באמצעות הכלים. "
        "צור את המשימה ושייך אותה למפתח המתאים לפי תוצאת החישוב, לאחר אישורי."
    )
    print("בקשת המשתמש:", request)
    result = agent.run(request)

    # רק החלטה מפורשת מהמשתמש יכולה לאשר פעולה ממתינה
    while result["status"] == "awaiting_approval":
        print("\nפעולה הממתינה לאישור:")
        print(json.dumps(result["pending_action"], ensure_ascii=False, indent=2))
        while True:
            answer = input("לאשר? (y/n): ").strip().lower()
            if answer in ("y", "n"):
                break
        result = agent.resume(answer == "y")

    print("\nתוצאה סופית:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\nמשימות במאגר המדומה:")
    print(json.dumps(client.list_issues(repo_owner="test-owner", repo_name="demo",
                                       state="open", timeout=3), ensure_ascii=False, indent=2))
    # התיעוד מכיל את נתוני הדמה והחלטות הסוכן בלבד
    output = Path("traces") / "gemini_demo.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"request": request, "result": result, "trace": agent.trace},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nTrace saved:", output)


if __name__ == "__main__":
    main()
