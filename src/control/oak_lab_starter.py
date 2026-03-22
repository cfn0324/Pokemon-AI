"""Deterministic helper for the Oak Lab starter handoff."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class OakLabStarterController:
    """Handle the exact last Oak prompt before free movement returns."""

    # These hashes correspond to the stable prompt pages that do not depend on
    # the player's chosen name.
    _PROMPT_HASH_TO_STEPS = {
        "f152ef346d4d1a5414e6edb7f5e98d90": ["a", "a", "down"],
        "0c512922c5124e91091885e663ffb2d7": ["a", "down"],
    }

    def __init__(self) -> None:
        self._pending_steps: List[str] = []

    def reset(self) -> None:
        """Forget any queued Oak-lab starter actions."""
        self._pending_steps = []

    def maybe_decide(
        self,
        current_state: Dict[str, Any],
        screen_hash: Optional[str],
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

        if map_id != 40:
            self.reset()
            return None

        if self._pending_steps:
            # The queued down-step is only safe while Oak is still directly above
            # the player at the starter table handoff position.
            if (x, y) != (5, 3):
                self.reset()
                return None
            action = self._pending_steps.pop(0)
            return {
                "action": action,
                "reasoning": "Auto: finish Oak's final starter question, then step away as soon as movement returns",
                "goal_update": None,
                "recorded_in_context": False,
            }

        if (x, y) != (5, 3) or direction != "up":
            return None

        steps = self._PROMPT_HASH_TO_STEPS.get(screen_hash or "")
        if not steps:
            return None

        self._pending_steps = list(steps)
        action = self._pending_steps.pop(0)
        return {
            "action": action,
            "reasoning": "Auto: advance Oak's final starter prompt without overshooting the first free-movement frame",
            "goal_update": None,
            "recorded_in_context": False,
        }
