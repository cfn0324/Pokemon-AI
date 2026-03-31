import time
import unittest

from src.agents.main_agent import MainAgent


class _ConfigStub:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)


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


if __name__ == "__main__":
    unittest.main()
