"""Deterministic helper for the Oak Lab starter handoff."""

from __future__ import annotations

from typing import Any, Dict, Optional


class OakLabStarterController:
    """Drive the fixed Oak Lab starter sequence until the first Pokemon is obtained."""

    _CLEAR_TABLE_HASH = "b141e2771ba1c9b2e7de784d6310e24f"

    def __init__(self) -> None:
        self._right_branch_started = False

    def reset(self) -> None:
        """Forget any in-progress Oak-lab starter phase."""
        self._right_branch_started = False

    def maybe_decide(
        self,
        current_state: Dict[str, Any],
        screen_hash: Optional[str],
        screen_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return a deterministic starter-handoff action when applicable."""
        memory = current_state.get("memory", {}) or {}
        if memory.get("party") or memory.get("in_battle"):
            self.reset()
            return None

        position = memory.get("position", {}) or {}
        map_id = int(position.get("map_id", -1) or -1)
        x = int(position.get("x", -1) or -1)
        y = int(position.get("y", -1) or -1)
        direction = str(memory.get("direction") or "").strip().lower()
        ui_state = memory.get("ui", {}) or {}
        normalized_screen = (screen_type or "").strip().lower()
        current_hash = screen_hash or ""

        if map_id != 40:
            self.reset()
            return None

        if (x, y) != (5, 3):
            if self._right_branch_started:
                return None
            return None

        if direction == "right":
            self._right_branch_started = True
            return {
                "action": "a",
                "reasoning": "Auto: keep advancing Oak Lab's right-side starter branch until the first Pokemon is received",
                "goal_update": None,
                "recorded_in_context": False,
            }

        if self._right_branch_started:
            return {
                "action": "right",
                "reasoning": "Auto: realign with Oak Lab's starter table so the fixed right-side script can continue",
                "goal_update": None,
                "recorded_in_context": False,
            }

        if direction != "up":
            return None

        if normalized_screen == "indoor" or current_hash == self._CLEAR_TABLE_HASH:
            self._right_branch_started = True
            return {
                "action": "right",
                "reasoning": "Auto: pivot toward Oak Lab's starter table and enter the right-side starter branch",
                "goal_update": None,
                "recorded_in_context": False,
            }

        return {
            "action": "a",
            "reasoning": "Auto: advance Oak's starter-selection dialogue until the table branch is ready",
            "goal_update": None,
            "recorded_in_context": False,
        }
