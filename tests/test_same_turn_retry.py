import time
import unittest

from main import PokemonAIAgent
from src.agents.main_agent import AIDecisionRetrySignal, MainAgent
from src.control.decision_engine import DecisionContext


class _ConfigStub:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)


class _LoggerStub:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)


class _DecisionEngineStub:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def decide(self, context):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class SameTurnRetryTests(unittest.TestCase):
    def test_main_agent_raises_retry_signal_during_cooldown_in_pure_llm_mode(self):
        agent = object.__new__(MainAgent)
        agent.config = _ConfigStub(
            {
                "decision.pure_llm_mode": True,
                "decision.retry_same_turn_on_ai_error": True,
            }
        )
        agent._api_cooldown_until = time.time() + 0.5

        with self.assertRaises(AIDecisionRetrySignal) as exc_info:
            agent.decide_action({"turn": 1}, "state")

        self.assertEqual(exc_info.exception.source, "ai_cooldown")
        self.assertGreater(exc_info.exception.retry_after_seconds, 0.0)

    def test_main_agent_raises_retry_signal_during_cooldown_in_llm_primary_mode(self):
        agent = object.__new__(MainAgent)
        agent.config = _ConfigStub(
            {
                "decision.llm_primary_mode": True,
                "decision.retry_same_turn_on_ai_error": True,
            }
        )
        agent._api_cooldown_until = time.time() + 0.5

        with self.assertRaises(AIDecisionRetrySignal) as exc_info:
            agent.decide_action({"turn": 1}, "state")

        self.assertEqual(exc_info.exception.source, "ai_cooldown")
        self.assertGreater(exc_info.exception.retry_after_seconds, 0.0)

    def test_same_turn_retry_retries_before_returning_a_decision(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "decision.pure_llm_mode": True,
                "decision.retry_same_turn_on_ai_error": True,
                "decision.same_turn_retry_max_attempts": 3,
                "decision.same_turn_retry_timeout_seconds": 5,
                "decision.same_turn_retry_min_delay_seconds": 0,
            }
        )
        agent.turn_count = 42
        agent.logger = _LoggerStub()
        agent.decision_engine = _DecisionEngineStub(
            [
                AIDecisionRetrySignal("temporary provider failure", source="ai_error", retry_after_seconds=0),
                {"action": "a", "reasoning": "ok", "recorded_in_context": True},
            ]
        )

        decision = agent._decide_action_for_current_turn(
            DecisionContext(current_state={"turn": 42}, state_text="state", screen_type=None)
        )

        self.assertEqual(decision["action"], "a")
        self.assertEqual(agent.decision_engine.calls, 2)
        self.assertEqual(len(agent.logger.warnings), 1)

    def test_same_turn_retry_retries_before_returning_a_decision_in_llm_primary_mode(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "decision.llm_primary_mode": True,
                "decision.retry_same_turn_on_ai_error": True,
                "decision.same_turn_retry_max_attempts": 3,
                "decision.same_turn_retry_timeout_seconds": 5,
                "decision.same_turn_retry_min_delay_seconds": 0,
            }
        )
        agent.turn_count = 43
        agent.logger = _LoggerStub()
        agent.decision_engine = _DecisionEngineStub(
            [
                AIDecisionRetrySignal("temporary provider failure", source="ai_error", retry_after_seconds=0),
                {"action": "a", "reasoning": "ok", "recorded_in_context": True},
            ]
        )

        decision = agent._decide_action_for_current_turn(
            DecisionContext(current_state={"turn": 43}, state_text="state", screen_type=None)
        )

        self.assertEqual(decision["action"], "a")
        self.assertEqual(agent.decision_engine.calls, 2)
        self.assertEqual(len(agent.logger.warnings), 1)

    def test_same_turn_retry_raises_after_budget_exhaustion(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "decision.pure_llm_mode": True,
                "decision.retry_same_turn_on_ai_error": True,
                "decision.same_turn_retry_max_attempts": 2,
                "decision.same_turn_retry_timeout_seconds": 1,
                "decision.same_turn_retry_min_delay_seconds": 0,
            }
        )
        agent.turn_count = 7
        agent.logger = _LoggerStub()
        agent.decision_engine = _DecisionEngineStub(
            [
                AIDecisionRetrySignal("temporary provider failure", source="ai_error", retry_after_seconds=0),
                AIDecisionRetrySignal("still failing", source="ai_error", retry_after_seconds=0),
            ]
        )

        with self.assertRaises(RuntimeError) as exc_info:
            agent._decide_action_for_current_turn(
                DecisionContext(current_state={"turn": 7}, state_text="state", screen_type=None)
            )

        self.assertIn("retry budget exhausted", str(exc_info.exception).lower())


if __name__ == "__main__":
    unittest.main()
