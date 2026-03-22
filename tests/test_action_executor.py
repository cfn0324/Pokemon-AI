import unittest

from src.tools.action_executor import ActionExecutor


class _DummyLogger:
    def warning(self, *args, **kwargs):
        return None

    def debug(self, *args, **kwargs):
        return None


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


if __name__ == "__main__":
    unittest.main()
