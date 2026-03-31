import unittest

from src.agents.async_decision import AsyncDecisionMaker
from src.agents.main_agent import AIDecisionRetrySignal


class _ConfigStub:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)


class _MainAgentRetryStub:
    def __init__(self, outcomes, config=None):
        self.outcomes = list(outcomes)
        self.config = _ConfigStub(
            config
            or {
                "decision.retry_same_turn_on_ai_error": True,
                "decision.same_turn_retry_max_attempts": 3,
                "decision.same_turn_retry_timeout_seconds": 5,
                "decision.same_turn_retry_min_delay_seconds": 0,
            }
        )
        self.calls = 0

    def decide_action(self, current_state, state_text, screenshot_bytes=None):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class AsyncDecisionRetryTests(unittest.TestCase):
    def test_async_decision_maker_retries_retry_signal_before_returning_decision(self):
        main_agent = _MainAgentRetryStub(
            [
                AIDecisionRetrySignal("temporary failure", source="ai_error", retry_after_seconds=0),
                {"action": "a", "reasoning": "ok", "decision_source": "ai", "decision_path": "ai"},
            ]
        )
        maker = AsyncDecisionMaker(main_agent)

        decision = maker._decide_with_retry({"turn": 1}, "state")

        self.assertEqual(decision["action"], "a")
        self.assertEqual(main_agent.calls, 2)


if __name__ == "__main__":
    unittest.main()
