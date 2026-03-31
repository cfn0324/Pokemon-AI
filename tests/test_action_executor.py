import unittest

from src.tools.action_executor import ActionExecutor


class _DummyLogger:
    def warning(self, *args, **kwargs):
        return None

    def debug(self, *args, **kwargs):
        return None

    def action(self, *args, **kwargs):
        return None


class _ConfigStub:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)


class _EmulatorStub:
    def __init__(self):
        self.presses = []
        self.ticks = []

    def press_button(self, action):
        self.presses.append(action)

    def tick(self, frames):
        self.ticks.append(frames)


class ActionExecutorStuckTests(unittest.TestCase):
    def _build_executor(self, actions):
        executor = ActionExecutor.__new__(ActionExecutor)
        executor.last_actions = list(actions)
        executor.stuck_threshold = len(actions)
        executor.logger = _DummyLogger()
        return executor

    def test_dialogue_ui_does_not_count_as_stuck_for_repeated_confirm(self):
        executor = self._build_executor(["a"] * 10)
        self.assertFalse(
            executor.is_stuck(
                screen_type="dialogue",
                ui_state={"text_box_active": True, "menu_active": False},
            )
        )

    def test_repeated_direction_without_ui_still_counts_as_stuck(self):
        executor = self._build_executor(["left"] * 10)
        self.assertTrue(executor.is_stuck(screen_type="indoor", ui_state={}))


class ActionExecutorPureLLMTests(unittest.TestCase):
    def test_direction_execute_uses_single_press_in_pure_llm_mode(self):
        executor = ActionExecutor.__new__(ActionExecutor)
        executor.emulator = _EmulatorStub()
        executor.memory_reader = None
        executor.config = _ConfigStub(
            {
                "decision.pure_llm_mode": True,
                "actions.delay_ms": 0,
                "actions.direction_settle_frames": 0,
            }
        )
        executor.logger = _DummyLogger()
        executor.action_delay = 0.0
        executor.last_actions = []
        executor.stuck_threshold = 10

        success = executor.execute("up")

        self.assertTrue(success)
        self.assertEqual(executor.emulator.presses, ["up"])

    def test_direction_execute_uses_single_press_in_llm_primary_mode(self):
        executor = ActionExecutor.__new__(ActionExecutor)
        executor.emulator = _EmulatorStub()
        executor.memory_reader = None
        executor.config = _ConfigStub(
            {
                "decision.llm_primary_mode": True,
                "actions.delay_ms": 0,
                "actions.direction_settle_frames": 0,
            }
        )
        executor.logger = _DummyLogger()
        executor.action_delay = 0.0
        executor.last_actions = []
        executor.stuck_threshold = 10

        success = executor.execute("up")

        self.assertTrue(success)
        self.assertEqual(executor.emulator.presses, ["up"])


if __name__ == "__main__":
    unittest.main()
