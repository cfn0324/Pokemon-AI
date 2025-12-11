"""Action executor for translating decisions to button presses."""

from typing import List, Optional
import time

from ..emulator.game_boy import GameBoyEmulator
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

    def __init__(self, emulator: GameBoyEmulator):
        """Initialize action executor.

        Args:
            emulator: GameBoy emulator instance
        """
        self.emulator = emulator
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
            time.sleep(0.5)
        else:
            self.emulator.press_button(action)

        # Delay between actions
        time.sleep(self.action_delay)

        return True

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

    def is_stuck(self) -> bool:
        """Check if agent appears to be stuck (repeating same action).

        Returns:
            True if stuck
        """
        if len(self.last_actions) < self.stuck_threshold:
            return False

        # Check if all recent actions are the same
        if len(set(self.last_actions)) == 1:
            self.logger.warning(f"Stuck detected: repeating '{self.last_actions[0]}' {len(self.last_actions)} times")
            return True

        # Check if alternating between two actions
        if len(set(self.last_actions)) == 2:
            # Could be stuck in a loop
            pattern = self.last_actions[-4:]
            if pattern[0] == pattern[2] and pattern[1] == pattern[3]:
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
