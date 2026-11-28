"""

מתאם גמנאי לממשק ההחלטות של לולאת הסוכן

"""

import json
import os
from src.prompts import SYSTEM_PROMPT


class GeminiModel:
    def __init__(self, api_key=None, model_name="gemini-3.5-flash-lite", client=None):
        self.model_name = model_name
        # הזרקת לקוח מדומה מאפשרת בדיקות ללא רשת וללא מפתח API
        if client is None:
            key = api_key or os.environ.get("GEMINI_API_KEY")
            if not key:
                raise ValueError("GEMINI_API_KEY is required.")
            from google import genai
            client = genai.Client(api_key=key)
        self.client = client

    def decide(self, context, tools):
        # חוזי הכלים וההקשר נשלחים כנתונים; ההנחיות נשלחות בנפרד
        payload = json.dumps({"context": context, "tools": tools},
                             ensure_ascii=False, allow_nan=False)
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=payload,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        )
        # המודל רק מציע החלטה. לולאת הסוכן והנתב בודקים ומבצעים אותה
        decision = json.loads(response.text)
        if not isinstance(decision, dict):
            raise ValueError("Model decision must be a JSON object.")
        return decision
