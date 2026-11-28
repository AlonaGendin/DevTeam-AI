"""

בדיקות למתאם המודל ללא קריאה לשירות חיצוני

"""

import json
from types import SimpleNamespace
import pytest
from src.gemini_model import GeminiModel
from src.prompts import SYSTEM_PROMPT


class FakeClient:
    def __init__(self, response_text):
        self.response_text = response_text
        self.calls = []
        self.models = self

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=self.response_text)


def test_tool_decision():
    expected = {"action": "tool", "tool_name": "get_team_members",
                "inputs": {"project_id": "project-1"}}
    model = GeminiModel(client=FakeClient(json.dumps(expected)))
    assert model.decide({}, []) == expected


def test_final_decision():
    expected = {"action": "final", "message": "התכנון הושלם"}
    model = GeminiModel(client=FakeClient(json.dumps(expected)))
    assert model.decide({}, []) == expected


def test_context_and_contracts_sent_as_data():
    client = FakeClient('{"action":"clarify","message":"Missing availability"}')
    context = {"messages": [{"role": "user", "content": "תכנן עבודה"}]}
    tools = [{"name": "get_team_members"}]
    GeminiModel(client=client).decide(context, tools)
    call = client.calls[0]
    assert json.loads(call["contents"]) == {"context": context, "tools": tools}
    assert call["config"]["system_instruction"] == SYSTEM_PROMPT
    assert call["config"]["response_mime_type"] == "application/json"


def test_invalid_json_rejected():
    with pytest.raises(json.JSONDecodeError):
        GeminiModel(client=FakeClient("not JSON")).decide({}, [])


def test_non_object_rejected():
    with pytest.raises(ValueError):
        GeminiModel(client=FakeClient("[]")).decide({}, [])


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiModel()


def test_model_name_configurable():
    client = FakeClient('{"action":"final","message":"Done"}')
    GeminiModel(model_name="test-model", client=client).decide({}, [])
    assert client.calls[0]["model"] == "test-model"
