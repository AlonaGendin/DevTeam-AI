"""

קובץ זה אחראי על ניהול הזיכרון ותקציב ההקשר של הסוכן

מאפשר שמירת מידע חשוב באמצעות פתקים
בניית הקשר מלא ובניית הקשר מצומצם 
הכולל את הפתקים ואת ארבע ההודעות האחרונות

"""

from copy import deepcopy


# שמירת פתק בזיכרון
def save_note(state, key, value):
    state.notes[key] = deepcopy(value)


# שליפת פתק מהזיכרון
def get_note(state, key, default=None):
    return deepcopy(state.notes.get(key, default))


# מחיקת פתק מהזיכרון
def delete_note(state, key):
    state.notes.pop(key, None)


# בניית הקשר מלא
def build_full_context(state, system_prompt):
    return {
        "system_prompt": system_prompt,
        "notes": deepcopy(state.notes),
        "messages": deepcopy(state.messages)
    }


# בניית הקשר מצומצם
def build_reduced_context(state, system_prompt):
    return {
        "system_prompt": system_prompt,
        "notes": deepcopy(state.notes),
        "messages": deepcopy(state.messages[-4:])
    }