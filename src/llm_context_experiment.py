"""
קובץ זה מבצע ניסוי להשוואה בין הקשר מלא
לבין הקשר מצומצם באמצעות מודל השפה גמנאי

אותה שאלה נשלחת למודל בשני סוגי ההקשר
התשובות נבדקות מול תוצאה צפויה שהוגדרה מראש

הניסוי משווה
- נכונות התשובות
- זהות בין התשובות
- מספר הטוקנים בקלט
- זמני התגובה

"""

import os
import json
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from src.state import AgentState
from src.memory import (
    save_note,
    build_full_context,
    build_reduced_context
)

MODEL = "gemini-3.5-flash-lite"

# השאלה הזהה שתישלח בשתי ההרצות
QUESTION = """
List the project tasks and their estimated hours,
the availability of each team member,
the total required hours, total available hours,
remaining hours and whether capacity is sufficient.

Return only a JSON object with these fields:
tasks, team, required_hours, available_hours,
remaining_hours, capacity_sufficient.

Each task must contain title and estimated_hours.
Use the original task titles and team member names.
"""

# הגדרת התשובה הצפויה מראש
EXPECTED_ANSWER = {
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


# יצירת מצב סוכן והיסטוריית שיחה לניסוי
def create_test_state():

    state = AgentState("user1", "session1")

    # שמירת המידע החשוב בפתקים
    save_note(state, "repository", "DevTeam-AI")

    save_note(state, "team", {
        "ortal": 10,
        "alona": 8
    })

    save_note(state, "tasks", [
        {"title": "Login page", "estimated_hours": 4},
        {"title": "Database integration", "estimated_hours": 6},
        {"title": "Automated tests", "estimated_hours": 3}
    ])

    # יצירת אותה היסטוריית שיחה מהניסוי הקודם
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

    return state


# שליחת ההקשר והשאלה למודל
def ask_model(client, context):

    prompt = (
        json.dumps(context, ensure_ascii=False)
        + "\n\n"
        + QUESTION
    )

    # מדידת זמן התגובה
    start_time = time.perf_counter()

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json"
        )
    )

    elapsed_time = time.perf_counter() - start_time

    # המרת תשובת המודל למילון
    answer = json.loads(response.text)

    # קבלת מספר הטוקנים בפועל מהמודל
    tokens = response.usage_metadata.prompt_token_count

    return answer, tokens, elapsed_time


# השוואת התשובה לתוצאה הצפויה
def check_answer(answer):

    differences = {}

    for key, expected in EXPECTED_ANSWER.items():

        actual = answer.get(key)

        # סדר המשימות אינו משפיע על נכונות התשובה
        if key == "tasks" and isinstance(actual, list):
            actual = sorted(actual, key=lambda task: task["title"])
            expected = sorted(expected, key=lambda task: task["title"])

        if actual != expected:
            differences[key] = {
                "expected": expected,
                "actual": actual
            }

    return differences


# הרצת הניסוי
def run_experiment():

    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing")

    client = genai.Client(api_key=api_key)

    state = create_test_state()

    system_prompt = "You are a Project Manager Agent."

    # בניית שני סוגי ההקשר
    full = build_full_context(state, system_prompt)
    reduced = build_reduced_context(state, system_prompt)

    # הרצת אותה שאלה בשני סוגי ההקשר
    print("Running full context...")
    full_answer, full_tokens, full_time = ask_model(client, full)

    print("Running reduced context...")
    reduced_answer, reduced_tokens, reduced_time = ask_model(
        client, reduced
    )

    # בדיקת נכונות התשובות
    full_errors = check_answer(full_answer)
    reduced_errors = check_answer(reduced_answer)

    # חישוב אחוז החיסכון בטוקנים
    token_reduction = (
        1 - reduced_tokens / full_tokens
    ) * 100

    # הצגת תוצאות ההקשר המלא
    print("\n=== Full Context ===")
    print(json.dumps(full_answer, indent=2))
    print(f"Correct: {not full_errors}")
    print(f"Errors: {full_errors}")
    print(f"Input tokens: {full_tokens}")
    print(f"Response time: {full_time:.2f} seconds")

    # הצגת תוצאות ההקשר המצומצם
    print("\n=== Reduced Context ===")
    print(json.dumps(reduced_answer, indent=2))
    print(f"Correct: {not reduced_errors}")
    print(f"Errors: {reduced_errors}")
    print(f"Input tokens: {reduced_tokens}")
    print(f"Response time: {reduced_time:.2f} seconds")

    # סיכום ההשוואה
    print("\n=== Comparison ===")
    print(f"Answers identical: {full_answer == reduced_answer}")
    print(f"Token reduction: {token_reduction:.2f}%")
    print(f"Both answers correct: {not full_errors and not reduced_errors}")


if __name__ == "__main__":
    run_experiment()