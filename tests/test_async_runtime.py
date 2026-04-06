import unittest

from main import PokemonAIAgent


class _ConfigStub:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)


class _AsyncAIStub:
    def __init__(self, *, running=True, thinking=False, decision=None, queue_ok=True):
        self.running = running
        self.is_thinking = thinking
        self._decision = decision
        self.queue_ok = queue_ok
        self.requests = []

    def get_decision(self, timeout=0.0):
        decision = self._decision
        self._decision = None
        return decision

    def request_decision(self, current_state, state_text, screenshot_bytes=None):
        self.requests.append((current_state, state_text, screenshot_bytes))
        return self.queue_ok


class _MainAgentStub:
    def __init__(self):
        self.calls = []

    def decide_action(self, current_state, state_text, screenshot_bytes=None):
        self.calls.append((current_state, state_text, screenshot_bytes))
        return {"action": "a", "reasoning": "sync"}


class _ActionExecutorStub:
    def __init__(self):
        self.reset_calls = 0

    def reset_stuck_detection(self):
        self.reset_calls += 1


class _EmulatorStub:
    def __init__(self):
        self.ticks = []

    def tick(self, frames):
        self.ticks.append(frames)


class AsyncRealtimeTests(unittest.TestCase):
    def _make_agent(self, *, config=None, async_ai=None, main_agent=None):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(config or {"performance.async_decisions": True})
        agent.async_ai = async_ai or _AsyncAIStub()
        agent.main_agent = main_agent or _MainAgentStub()
        agent.action_executor = _ActionExecutorStub()
        agent.emulator = _EmulatorStub()
        return agent

    def test_async_ready_decision_is_returned_without_sync_fallback(self):
        agent = self._make_agent(
            async_ai=_AsyncAIStub(
                decision={"action": "left", "reasoning": "ready", "recorded_in_context": True}
            )
        )

        decision = agent._get_ai_decision_responsive({"turn": 1}, "state")

        self.assertEqual(decision["action"], "left")
        self.assertEqual(agent.main_agent.calls, [])
        self.assertEqual(agent.async_ai.requests, [])

    def test_async_pending_returns_lightweight_placeholder_and_queues_once(self):
        agent = self._make_agent(async_ai=_AsyncAIStub(thinking=False, decision=None, queue_ok=True))

        decision = agent._get_ai_decision_responsive({"turn": 2}, "state", b"img")

        self.assertEqual(decision["executor"], "async_background_wait")
        self.assertEqual(decision["action"], "thinking")
        self.assertTrue(decision["recorded_in_context"])
        self.assertEqual(len(agent.async_ai.requests), 1)
        self.assertEqual(agent.main_agent.calls, [])

    def test_background_wait_ticks_lightly_without_normal_action_executor(self):
        agent = self._make_agent(
            config={
                "performance.async_decisions": True,
                "actions.async_wait_frames": 3,
                "actions.async_wait_sleep_ms": 0,
            }
        )

        success = agent._execute_async_background_wait()

        self.assertTrue(success)
        self.assertEqual(agent.emulator.ticks, [3])
        self.assertEqual(agent.action_executor.reset_calls, 1)

    def test_sync_fallback_still_exists_when_async_disabled(self):
        main_agent = _MainAgentStub()
        agent = self._make_agent(
            config={"performance.async_decisions": False},
            async_ai=_AsyncAIStub(running=False),
            main_agent=main_agent,
        )

        decision = agent._get_ai_decision_responsive({"turn": 3}, "state")

        self.assertEqual(decision["action"], "a")
        self.assertEqual(len(main_agent.calls), 1)

    def test_pure_llm_mode_forces_sync_model_path_even_if_async_is_enabled(self):
        main_agent = _MainAgentStub()
        agent = self._make_agent(
            config={
                "performance.async_decisions": True,
                "decision.pure_llm_mode": True,
            },
            async_ai=_AsyncAIStub(running=True, thinking=False, decision=None, queue_ok=True),
            main_agent=main_agent,
        )

        decision = agent._get_ai_decision_responsive({"turn": 4}, "state", b"img")

        self.assertEqual(decision["action"], "a")
        self.assertEqual(len(main_agent.calls), 1)
        self.assertEqual(agent.async_ai.requests, [])

    def test_disable_runtime_fallbacks_forces_sync_model_path_even_if_async_is_enabled(self):
        main_agent = _MainAgentStub()
        agent = self._make_agent(
            config={
                "performance.async_decisions": True,
                "decision.disable_runtime_fallbacks": True,
            },
            async_ai=_AsyncAIStub(running=True, thinking=False, decision=None, queue_ok=True),
            main_agent=main_agent,
        )

        decision = agent._get_ai_decision_responsive({"turn": 4}, "state", b"img")

        self.assertEqual(decision["action"], "a")
        self.assertEqual(len(main_agent.calls), 1)
        self.assertEqual(agent.async_ai.requests, [])

    def test_llm_primary_mode_uses_async_model_path_when_async_is_enabled(self):
        main_agent = _MainAgentStub()
        agent = self._make_agent(
            config={
                "performance.async_decisions": True,
                "decision.llm_primary_mode": True,
            },
            async_ai=_AsyncAIStub(running=True, thinking=False, decision=None, queue_ok=True),
            main_agent=main_agent,
        )

        decision = agent._get_ai_decision_responsive({"turn": 5}, "state", b"img")

        self.assertEqual(decision["executor"], "async_background_wait")
        self.assertEqual(main_agent.calls, [])
        self.assertEqual(len(agent.async_ai.requests), 1)

    def test_llm_primary_mode_still_falls_back_to_sync_when_async_disabled(self):
        main_agent = _MainAgentStub()
        agent = self._make_agent(
            config={
                "performance.async_decisions": False,
                "decision.llm_primary_mode": True,
            },
            async_ai=_AsyncAIStub(running=False),
            main_agent=main_agent,
        )

        decision = agent._get_ai_decision_responsive({"turn": 6}, "state", b"img")

        self.assertEqual(decision["action"], "a")
        self.assertEqual(len(main_agent.calls), 1)

    def test_dialogue_wait_is_rewritten_to_a(self):
        agent = self._make_agent()

        decision = agent._rewrite_wait_decision(
            {
                "action": "wait",
                "reasoning": "Need to wait for the dialogue to advance",
                "decision_source": "ai",
            },
            {"memory": {"ui": {"text_box_active": True}}},
            "dialogue",
        )

        self.assertEqual(decision["action"], "a")
        self.assertNotEqual(decision.get("executor"), "async_background_wait")

    def test_startup_wait_is_rewritten_to_passive_progress(self):
        agent = self._make_agent()

        decision = agent._rewrite_wait_decision(
            {
                "action": "wait",
                "reasoning": "Need to wait through boot",
                "decision_source": "ai",
            },
            {"memory": {"ui": {}}},
            "startup",
        )

        self.assertEqual(decision["action"], "progress")
        self.assertEqual(decision["executor"], "async_background_wait")
        self.assertTrue(decision["recorded_in_context"])

    def test_allow_wait_preserves_intentional_runtime_wait(self):
        agent = self._make_agent()

        decision = agent._rewrite_wait_decision(
            {
                "action": "wait",
                "reasoning": "Let the doorway auto-step settle",
                "decision_source": "post_warp_reentry_guard",
                "allow_wait": True,
            },
            {"memory": {"ui": {}}},
            "overworld",
        )

        self.assertEqual(decision["action"], "wait")
        self.assertTrue(decision["allow_wait"])

    def test_disable_runtime_fallbacks_preserves_wait_without_rewrite(self):
        agent = self._make_agent(
            config={"decision.disable_runtime_fallbacks": True}
        )

        decision = agent._rewrite_wait_decision(
            {
                "action": "wait",
                "reasoning": "API cooldown active",
                "decision_source": "ai_cooldown",
            },
            {"memory": {"ui": {"text_box_active": True}}},
            "dialogue",
        )

        self.assertEqual(decision["action"], "wait")
        self.assertEqual(decision["decision_source"], "ai_cooldown")


if __name__ == "__main__":
    unittest.main()
