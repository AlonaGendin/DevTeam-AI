"""

מודל מדומה עם סדר החלטות קבוע מראש לצורך בדיקות חוזרות

"""

from copy import deepcopy


class MockModel:
    def __init__(self, decisions):
        self.decisions = deepcopy(list(decisions))
        self.calls = []

    def decide(self, context, tools):
        # שמירת ההקשר מאפשרת לבדוק מה הועבר למודל בכל קריאה
        self.calls.append(deepcopy({"context": context, "tools": tools}))
        if not self.decisions:
            raise RuntimeError("No scripted decision remains.")
        return deepcopy(self.decisions.pop(0))
