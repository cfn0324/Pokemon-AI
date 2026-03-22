import unittest

from src.control.decision_engine import DecisionContext, DecisionEngine


class DecisionEngineTests(unittest.TestCase):
    def setUp(self):
        self.context = DecisionContext(
            current_state={"turn": 1},
            state_text="state",
            screen_type="dialogue",
            screenshot_bytes=None,
            screen_hash=None,
        )

    def test_first_matching_stage_wins_and_trace_is_recorded(self):
        engine = DecisionEngine(
            stages=[
                ("noop", lambda context: None),
                ("tool_stage", lambda context: {"action": "a", "reasoning": "tool"}),
                ("later", lambda context: {"action": "b", "reasoning": "later"}),
            ],
            fallback=lambda context: {"action": "wait", "reasoning": "fallback"},
        )

        decision = engine.decide(self.context)

        self.assertEqual(decision["action"], "a")
        self.assertEqual(decision["decision_source"], "tool_stage")
        self.assertEqual(decision["decision_path"], "tool")
        self.assertEqual(
            decision["decision_trace"],
            [
                {"stage": "noop", "matched": False},
                {"stage": "tool_stage", "matched": True},
            ],
        )

    def test_fallback_is_used_when_no_stage_matches(self):
        engine = DecisionEngine(
            stages=[("noop", lambda context: None)],
            fallback=lambda context: {"action": "wait", "reasoning": "fallback"},
        )

        decision = engine.decide(self.context)

        self.assertEqual(decision["decision_source"], "ai")
        self.assertEqual(decision["decision_path"], "ai")
        self.assertEqual(
            decision["decision_trace"],
            [{"stage": "noop", "matched": False}],
        )


if __name__ == "__main__":
    unittest.main()
