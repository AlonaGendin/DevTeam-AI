"""

קובץ זה מבצע ניסוי להשוואה בין הקשר מלא
לבין הקשר מצומצם המבוסס על פתקים וארבע הודעות אחרונות

הניסוי מודד את גודל ההקשר ואת אחוז החיסכון
ובודק האם המידע החשוב נשמר בהקשר המצומצם

"""

import json
import tiktoken

from src.state import AgentState
from src.memory import (
    save_note,
    build_full_context,
    build_reduced_context
)

# הפקת סיכום הפרויקט מתוך ההקשר
def mock_answer(context):
    notes = context["notes"]

    tasks = notes.get("tasks", [])
    team = notes.get("team", {})

    required_hours = sum(
        task["estimated_hours"] for task in tasks
    )

    available_hours = sum(team.values())

    return {
        "tasks": tasks,
        "team": team,
        "required_hours": required_hours,
        "available_hours": available_hours,
        "remaining_hours": available_hours - required_hours,
        "capacity_sufficient": available_hours >= required_hours
    }

def run_experiment():

    state = AgentState("user1", "session1")

    system_prompt = "You are a Project Manager Agent."

    # שמירת מידע חשוב בפתקים
    save_note(state, "repository", "DevTeam-AI")
    save_note(state, "team", {
        "ortal": 10,
        "alona": 8
    })

    # שמירת המשימות והערכת שעות העבודה
    save_note(state, "tasks", [
        {"title": "Login page", "estimated_hours": 4},
        {"title": "Database integration", "estimated_hours": 6},
        {"title": "Automated tests", "estimated_hours": 3}
    ])

    # יצירת היסטוריית שיחה לדוגמה
    messages = [
        ("user", "Our repository is DevTeam-AI."),
        ("assistant", "Repository information saved."),
        ("user", "Ortal is available for 10 hours."),
        ("assistant", "Availability saved."),
        ("user", "Alona is available for 8 hours."),
        ("assistant", "Availability saved."),
        ("user", "We need to develop a login page."),
        ("assistant", "The login page requires 4 hours."),
        ("user", "We also need database integration."),
        ("assistant", "Database integration requires 6 hours."),
        ("user", "We need automated tests."),
        ("assistant", "Testing requires 3 hours."),
        ("user", "Can you assign the tasks?"),
        ("assistant", "I will check team availability.")
    ]

    for role, content in messages:
        state.add_message(role, content)

    # בניית שני סוגי ההקשר
    full = build_full_context(state, system_prompt)
    reduced = build_reduced_context(state, system_prompt)

    # מדידת גודל ההקשר בתווים
    full_size = len(json.dumps(full, ensure_ascii=False))
    reduced_size = len(json.dumps(reduced, ensure_ascii=False))

    # חישוב אחוז החיסכון
    reduction = (1 - reduced_size / full_size) * 100

    # בדיקה האם המידע החשוב נשמר
    information_preserved = (
        full["notes"] == reduced["notes"]
        and full["system_prompt"] == reduced["system_prompt"]
        and reduced["messages"] == full["messages"][-4:]
    )

    # הצגת תוצאות הניסוי
    print("=== Context Comparison ===")
    print(f"Full messages: {len(full['messages'])}")
    print(f"Reduced messages: {len(reduced['messages'])}")
    print(f"Full context size: {full_size} characters")
    print(f"Reduced context size: {reduced_size} characters")
    print(f"Context reduction: {reduction:.2f}%")
    print(f"Saved information preserved: {information_preserved}")


    # מדידת מספר הטוקנים בהקשר
    encoding = tiktoken.get_encoding("o200k_base")

    full_tokens = len(encoding.encode(
        json.dumps(full, ensure_ascii=False)
    ))

    reduced_tokens = len(encoding.encode(
        json.dumps(reduced, ensure_ascii=False)
    ))

    token_reduction = (
        1 - reduced_tokens / full_tokens
    ) * 100

    print(f"Full context tokens: {full_tokens}")
    print(f"Reduced context tokens: {reduced_tokens}")
    print(f"Token reduction: {token_reduction:.2f}%")

        # הגדרת התוצאה הצפויה מראש
    expected_answer = {
        "tasks": [
            {"title": "Login page", "estimated_hours": 4},
            {"title": "Database integration", "estimated_hours": 6},
            {"title": "Automated tests", "estimated_hours": 3}
        ],
        "team": {
            "ortal": 10,
            "alona": 8
        },
        "required_hours": 13,
        "available_hours": 18,
        "remaining_hours": 5,
        "capacity_sufficient": True
    }

    # הפקת תשובה מכל סוג הקשר
    full_answer = mock_answer(full)
    reduced_answer = mock_answer(reduced)

    # השוואת התשובות לתוצאה הצפויה
    print("\n=== Answer Comparison ===")
    print(f"Full answer: {full_answer}")
    print(f"Reduced answer: {reduced_answer}")
    print(f"Full answer correct: {full_answer == expected_answer}")
    print(f"Reduced answer correct: {reduced_answer == expected_answer}")
    print(f"Answers identical: {full_answer == reduced_answer}")



if __name__ == "__main__":
    run_experiment()