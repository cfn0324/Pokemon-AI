import time
import unittest

from src.agents.main_agent import MainAgent


class _ConfigStub:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)


class _LoggerStub:
    def error(self, _message):
        pass

    def debug(self, _message):
        pass

    def warning(self, _message):
        pass

    def info(self, _message):
        pass

    def decision(self, _action, _reasoning):
        pass


class _ContextStub:
    def needs_summarization(self):
        return False

    def add_turn(self, *args, **kwargs):
        return None


class _GoalsStub:
    def sync_with_game_state(self, _game_state):
        return None


class MainAgentApiFailureTests(unittest.TestCase):
    def test_transport_failures_enter_api_cooldown(self):
        agent = object.__new__(MainAgent)
        agent.config = _ConfigStub(
            {
                "ai.api_error_cooldown_seconds": 2,
                "ai.api_error_cooldown_max_seconds": 10,
            }
        )
        agent._api_failure_count = 0
        agent._api_cooldown_until = 0.0

        agent._register_api_failure(
            "AI request failed: Failed to establish a new connection: [WinError 10013]"
        )

        self.assertEqual(agent._api_failure_count, 1)
        self.assertGreater(agent._api_cooldown_until, time.time())

    def test_persistent_provider_errors_are_not_same_turn_retryable(self):
        agent = object.__new__(MainAgent)
        agent.config = _ConfigStub({})

        retryable = agent._is_retryable_decision_error(
            RuntimeError("AI request failed with status 500: no available token")
        )

        self.assertFalse(retryable)

    def test_unreachable_transport_errors_are_not_same_turn_retryable(self):
        agent = object.__new__(MainAgent)
        agent.config = _ConfigStub({})

        retryable = agent._is_retryable_decision_error(
            RuntimeError(
                "AI request failed: HTTPConnectionPool(host='localhost', port=80): "
                "Max retries exceeded with url: /messages "
                "(Caused by NewConnectionError: Failed to establish a new connection: [WinError 10061])"
            )
        )

        self.assertFalse(retryable)

    def test_persistent_provider_errors_use_longer_cooldown(self):
        agent = object.__new__(MainAgent)
        agent.config = _ConfigStub(
            {
                "ai.api_error_cooldown_seconds": 2,
                "ai.api_error_cooldown_max_seconds": 4,
                "ai.persistent_api_error_cooldown_seconds": 15,
            }
        )
        agent._api_failure_count = 0
        agent._api_cooldown_until = 0.0

        before = time.time()
        agent._register_api_failure("AI request failed with status 500: no available token")

        self.assertEqual(agent._api_failure_count, 1)
        self.assertGreaterEqual(agent._api_cooldown_until - before, 14.0)

    def test_unreachable_transport_errors_use_extended_cooldown(self):
        agent = object.__new__(MainAgent)
        agent.config = _ConfigStub(
            {
                "ai.api_error_cooldown_seconds": 1,
                "ai.api_error_cooldown_max_seconds": 2,
                "ai.unreachable_api_error_cooldown_seconds": 12,
            }
        )
        agent._api_failure_count = 0
        agent._api_cooldown_until = 0.0

        before = time.time()
        agent._register_api_failure(
            "AI request failed: Failed to establish a new connection: [WinError 10061]"
        )

        self.assertEqual(agent._api_failure_count, 1)
        self.assertGreaterEqual(agent._api_cooldown_until - before, 11.0)

    def test_decide_action_returns_ai_error_instead_of_same_turn_retry_for_unreachable_host(self):
        agent = object.__new__(MainAgent)
        agent.config = _ConfigStub(
            {
                "decision.llm_primary_mode": True,
                "decision.retry_same_turn_on_ai_error": True,
                "ai.api_error_cooldown_seconds": 1,
                "ai.api_error_cooldown_max_seconds": 2,
            }
        )
        agent.logger = _LoggerStub()
        agent.goals = _GoalsStub()
        agent.context = _ContextStub()
        agent._api_failure_count = 0
        agent._api_cooldown_until = 0.0
        agent._refresh_task_notebook = lambda: None
        agent._build_prompt = lambda *_args, **_kwargs: "PROMPT"
        agent._request_model_response = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError(
                "AI request failed: HTTPConnectionPool(host='localhost', port=80): "
                "Max retries exceeded with url: /messages "
                "(Caused by NewConnectionError('<urllib3.connection.HTTPConnection object>: "
                "Failed to establish a new connection: [WinError 10061] actively refused'))"
            )
        )

        decision = agent.decide_action({"turn": 1}, "STATE")

        self.assertEqual(decision["action"], "wait")
        self.assertEqual(decision["decision_source"], "ai_error")
        self.assertGreater(agent._api_cooldown_until, time.time())


if __name__ == "__main__":
    unittest.main()
