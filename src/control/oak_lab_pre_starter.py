"""Deterministic helper for Oak's Lab before the first Pokemon is obtained."""

from __future__ import annotations

from typing import Any, Dict, Optional


class OakLabPreStarterController:
    """Route the player to Oak's starter prompt before the existing handoff logic."""

    _FINAL_PROMPT_HASHES = {
        "f152ef346d4d1a5414e6edb7f5e98d90",
        "0c512922c5124e91091885e663ffb2d7",
    }

    def reset(self) -> None:
        """The controller is stateless between turns."""
        return None

    def maybe_decide(
        self,
        current_state: Dict[str, Any],
        screen_type: Optional[str],
        screen_hash: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Return a deterministic action for Oak's Lab before the starter is obtained."""
        memory = current_state.get("memory", {}) or {}
        if memory.get("party") or memory.get("in_battle"):
            return None

        position = memory.get("position", {}) or {}
        map_id = int(position.get("map_id", -1) or -1)
        x = int(position.get("x", -1) or -1)
        y = int(position.get("y", -1) or -1)
        direction = str(memory.get("direction") or "").strip().lower()
        normalized_screen = (screen_type or "").strip().lower()

        if map_id != 40:
            return None

        if (
            (x, y) == (5, 3)
            and direction == "up"
            and (screen_hash or "") in self._FINAL_PROMPT_HASHES
        ):
            return None

        if normalized_screen == "dialogue":
            return self._decision(
                "a",
                "Auto: advance Oak Lab's pre-starter dialogue until free movement or the final starter prompt returns",
            )

        if (x, y) in {(4, 6), (5, 6)}:
            return self._decision(
                "a",
                "Auto: recover from Oak Lab's lower trigger zone and step back toward the starter table route",
            )

        if (x, y) == (5, 3):
            return self._decision(
                "a",
                "Auto: start Oak's starter-selection dialogue from the correct table position",
            )

        action = self._route_action(x, y)
        if not action:
            return None

        return self._decision(
            action,
            "Auto: route through Oak's Lab toward the starter table before the first Pokemon is obtained",
        )

    def _route_action(self, x: int, y: int) -> Optional[str]:
        """Choose a safe recovery step toward the starter table."""
        if (x, y) == (5, 1):
            return "left"
        if (x, y) == (4, 1):
            return "down"
        if (x, y) == (4, 2):
            return "left"

        if x >= 6:
            if y < 4:
                return "down"
            return "left"

        if x == 5:
            if y > 3:
                return "up"
            if y < 3:
                return "left"
            return None

        if y > 5:
            return "up"
        if y < 5:
            return "down"
        return "right"

    def _decision(self, action: str, reasoning: str) -> Dict[str, Any]:
        """Build a deterministic control-layer decision payload."""
        return {
            "action": action,
            "reasoning": reasoning,
            "goal_update": None,
            "recorded_in_context": False,
        }
