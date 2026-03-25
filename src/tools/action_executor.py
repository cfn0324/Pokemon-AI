"""Action executor for translating decisions to button presses."""

from typing import Any, Dict, List, Optional
import time

from ..emulator.game_boy import GameBoyEmulator
from ..emulator.memory_reader import MemoryReader
from ..utils.logger import get_logger
from ..utils.config import get_config


class ActionExecutor:
    """Executes actions on the emulator."""

    # Valid actions
    VALID_ACTIONS = [
        'up', 'down', 'left', 'right',
        'a', 'b', 'start', 'select',
        'wait'
    ]

    def __init__(
        self,
        emulator: GameBoyEmulator,
        memory_reader: Optional[MemoryReader] = None,
    ):
        """Initialize action executor.

        Args:
            emulator: GameBoy emulator instance
            memory_reader: Optional memory reader for smarter movement retries
        """
        self.emulator = emulator
        self.memory_reader = memory_reader
        self.config = get_config()
        self.logger = get_logger('ActionExecutor')

        self.action_delay = self.config.get('actions.delay_ms', 100) / 1000.0
        self.last_actions: List[str] = []
        self.stuck_threshold = self.config.get('actions.stuck_threshold', 10)

        self.logger.info("Action executor initialized")

    def execute(self, action: str) -> bool:
        """Execute an action.

        Args:
            action: Action to execute

        Returns:
            True if successful
        """
        action = action.lower().strip()

        if action not in self.VALID_ACTIONS:
            self.logger.warning(f"Invalid action: {action}")
            return False

        self.logger.action(action)

        # Track for stuck detection
        self.last_actions.append(action)
        if len(self.last_actions) > self.stuck_threshold:
            self.last_actions.pop(0)

        # Execute the action
        if action == 'wait':
            # Sleep alone does not advance the emulator; tick some frames to let
            # dialogues/animations/scripts progress.
            wait_frames = int(self.config.get('actions.wait_frames', 30) or 30)
            self.emulator.tick(max(1, wait_frames))
            time.sleep(0.05)
        elif action in {'up', 'down', 'left', 'right'}:
            if self._pure_llm_mode_enabled():
                self.emulator.press_button(action)
            else:
                self._execute_direction(action)
        else:
            self.emulator.press_button(action)

        # Let movement/menu transitions settle before the next observation.
        self.emulator.tick(self._get_settle_frames(action))
        time.sleep(self.action_delay)

        return True

    def _pure_llm_mode_enabled(self) -> bool:
        """Return whether execution should avoid action-expanding helpers."""
        return bool(self.config.get('decision.pure_llm_mode', False))

    def _read_movement_snapshot(self) -> Optional[Dict[str, Any]]:
        """Read minimal movement-relevant state for smarter direction retries."""
        if not self.memory_reader:
            return None

        try:
            position = self.memory_reader.read_player_position()
            return {
                "map_id": int(position.get("map_id", 0)),
                "x": int(position.get("x", 0)),
                "y": int(position.get("y", 0)),
                "direction": self.memory_reader.read_player_direction(),
                "in_battle": bool(self.memory_reader.is_in_battle()),
                "ui": self.memory_reader.read_ui_state(),
            }
        except Exception:
            return None

    def _execute_direction(self, action: str) -> None:
        """Retry a direction press a few times so one action better approximates one step."""
        attempts = int(self.config.get('actions.direction_repeat_attempts', 4) or 4)
        wait_frames = int(self.config.get('actions.wait_frames', 30) or 30)
        settle_frames = int(self.config.get('actions.wait_settle_frames', 2) or 2)
        before = self._read_movement_snapshot()

        for attempt in range(max(1, attempts)):
            self.emulator.press_button(action)

            if not before:
                continue

            after = self._read_movement_snapshot()
            if not after:
                continue

            moved = (
                before["map_id"],
                before["x"],
                before["y"],
            ) != (
                after["map_id"],
                after["x"],
                after["y"],
            )
            if moved:
                return

            ui = after.get("ui", {})
            stale_menu_overlay = ui.get("menu_active") and ui.get("text_box_active")
            if after.get("in_battle") or (ui.get("menu_active") and not stale_menu_overlay):
                return

            if ui.get("text_box_active"):
                # Some scripted states leave the RAM dialogue flag stuck even after
                # free movement returns; give the overworld step time to resolve.
                self.emulator.tick(max(1, wait_frames))
                self.emulator.tick(max(0, settle_frames))
                after = self._read_movement_snapshot()
                if not after:
                    continue

                moved = (
                    before["map_id"],
                    before["x"],
                    before["y"],
                ) != (
                    after["map_id"],
                    after["x"],
                    after["y"],
                )
                if moved:
                    return

                ui = after.get("ui", {})
                stale_menu_overlay = ui.get("menu_active") and ui.get("text_box_active")
                if after.get("in_battle") or (ui.get("menu_active") and not stale_menu_overlay):
                    return

            # When the first press only changes facing, keep nudging in the same
            # direction instead of forcing the planner/LLM to rediscover that.
            if after.get("direction") == action and attempt < attempts - 1:
                continue

            before = after

    def _get_settle_frames(self, action: str) -> int:
        """Return post-action settle frames for stable observation."""
        if action in {'up', 'down', 'left', 'right'}:
            return max(0, int(self.config.get('actions.direction_settle_frames', 8) or 8))
        if action in {'a', 'b', 'start', 'select'}:
            return max(0, int(self.config.get('actions.button_settle_frames', 10) or 10))
        return max(0, int(self.config.get('actions.wait_settle_frames', 2) or 2))

    def execute_sequence(self, actions: List[str]) -> bool:
        """Execute a sequence of actions.

        Args:
            actions: List of actions

        Returns:
            True if all successful
        """
        self.logger.info(f"Executing sequence of {len(actions)} actions")

        for action in actions:
            if not self.execute(action):
                return False

        return True

    def is_stuck(
        self,
        screen_type: Optional[str] = None,
        ui_state: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if agent appears to be stuck (repeating same action).

        Returns:
            True if stuck
        """
        if len(self.last_actions) < self.stuck_threshold:
            return False

        ui_state = ui_state or {}
        screen = (screen_type or "").strip().lower()
        repeating = set(self.last_actions)
        text_or_menu_active = bool(ui_state.get("text_box_active") or ui_state.get("menu_active"))
        ui_like_screen = screen in {
            "dialogue",
            "cutscene",
            "text_entry",
            "naming_screen",
            "startup",
            "title",
            "startup_menu",
            "options_menu",
            "menu",
        }

        # Repeated confirm/wait inputs are normal while dialogue or menus are active.
        if (text_or_menu_active or ui_like_screen) and repeating.issubset({"a", "b", "wait", "start", "select"}):
            return False

        # Check if all recent actions are the same
        if len(repeating) == 1:
            repeated_action = self.last_actions[0]
            if repeated_action == "wait":
                return False
            self.logger.warning(f"Stuck detected: repeating '{self.last_actions[0]}' {len(self.last_actions)} times")
            return True

        # Check if alternating between two actions
        if len(repeating) == 2:
            # Could be stuck in a loop
            pattern = self.last_actions[-4:]
            if len(pattern) == 4 and pattern[0] != pattern[1] and pattern[0] == pattern[2] and pattern[1] == pattern[3]:
                self.logger.warning(f"Stuck detected: alternating pattern {pattern}")
                return True

        return False

    def reset_stuck_detection(self) -> None:
        """Reset stuck detection history."""
        self.last_actions.clear()
        self.logger.debug("Reset stuck detection")

    def get_action_history(self, n: int = 10) -> List[str]:
        """Get recent action history.

        Args:
            n: Number of recent actions

        Returns:
            List of recent actions
        """
        return self.last_actions[-n:]
