"""

קובץ זה מכיל בדיקות אוטומטיות לניהול הזיכרון
ולבניית ההקשר המועבר למודל

הבדיקות בוחנות שמירה עדכון ומחיקה של פתקים
הפרדה בין שיחות ומשתמשים ושמירת ארבע ההודעות
האחרונות בהקשר המצומצם

"""

from src.state import AgentState
from src.memory import (
    save_note,
    get_note,
    delete_note,
    build_full_context,
    build_reduced_context
)


# בדיקת שמירת פתק
def test_save_note():
    state = AgentState("user1", "session1")

    save_note(state, "availability", 10)

    assert get_note(state, "availability") == 10


# בדיקת עדכון פתק קיים
def test_update_note():
    state = AgentState("user1", "session1")

    save_note(state, "availability", 10)
    save_note(state, "availability", 15)

    assert get_note(state, "availability") == 15


# בדיקת מחיקת פתק
def test_delete_note():
    state = AgentState("user1", "session1")

    save_note(state, "availability", 10)
    delete_note(state, "availability")

    assert get_note(state, "availability") is None


# בדיקת שליפת פתק שאינו קיים
def test_missing_note():
    state = AgentState("user1", "session1")

    assert get_note(state, "unknown") is None


# בדיקת בניית הקשר מלא
def test_full_context():
    state = AgentState("user1", "session1")

    for i in range(10):
        state.add_message("user", f"Message {i}")

    context = build_full_context(state, "System prompt")

    assert len(context["messages"]) == 10
    assert context["system_prompt"] == "System prompt"


# בדיקת שמירת ארבע ההודעות האחרונות בלבד
def test_reduced_context():
    state = AgentState("user1", "session1")

    for i in range(10):
        state.add_message("user", f"Message {i}")

    context = build_reduced_context(state, "System prompt")

    assert len(context["messages"]) == 4
    assert context["messages"] == state.messages[-4:]
    assert context["system_prompt"] == "System prompt"


# בדיקת שמירת פתקים גם בהקשר מצומצם
def test_notes_in_reduced_context():
    state = AgentState("user1", "session1")

    save_note(state, "availability", 10)

    for i in range(10):
        state.add_message("user", f"Message {i}")

    context = build_reduced_context(state, "System prompt")

    assert context["notes"]["availability"] == 10


# בדיקת שיחה קצרה מארבע הודעות
def test_short_conversation():
    state = AgentState("user1", "session1")

    state.add_message("user", "Hello")
    state.add_message("assistant", "How can I help?")

    context = build_reduced_context(state, "System prompt")

    assert len(context["messages"]) == 2


# בדיקת הפרדת זיכרון בין שיחות
def test_memory_session_isolation():
    first = AgentState("user1", "session1")
    second = AgentState("user1", "session2")

    save_note(first, "availability", 10)

    assert get_note(second, "availability") is None


# בדיקת הפרדת זיכרון בין משתמשים
def test_memory_user_isolation():
    first = AgentState("user1", "session1")
    second = AgentState("user2", "session1")

    save_note(first, "availability", 10)

    assert get_note(second, "availability") is None


# בדיקת מניעת שינוי עקיף של הזיכרון
def test_note_copy():
    state = AgentState("user1", "session1")

    team = {"developer": 10}
    save_note(state, "team", team)

    team["developer"] = 20

    assert get_note(state, "team")["developer"] == 10

    retrieved = get_note(state, "team")
    retrieved["developer"] = 30

    assert get_note(state, "team")["developer"] == 10