"""Deterministic helper for Oak Lab after the first Pokemon is received."""

from __future__ import annotations

from typing import Any, Dict, Optional


class OakLabPostStarterController:
    """Bridge Oak Lab's post-starter handoff into the existing rival-battle route."""

    def reset(self) -> None:
        """The controller is stateless between turns."""
        return None

    def maybe_decide(
        self,
        current_state: Dict[str, Any],
        screen_type: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Return a deterministic action while the rival handoff is still door-locked."""
        memory = current_state.get("memory", {}) or {}
        position = memory.get("position", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        map_id = int(position.get("map_id", -1) or -1)
        x = int(position.get("x", -1) or -1)
        y = int(position.get("y", -1) or -1)
        normalized_screen = (screen_type or "").strip().lower()

        if map_id != 40:
            return None
        if not self._is_opening_party(memory):
            return None
        if memory.get("in_battle"):
            return None
        if ui_state.get("text_box_active") or ui_state.get("menu_active"):
            return None
        if normalized_screen not in {"indoor", "overworld"}:
            return None

        if (x, y) == (5, 3):
            return self._decision(
                "down",
                "Auto: keep prodding Oak Lab's post-starter doorway trigger until the rival handoff fully unlocks",
            )

        if (x, y) == (5, 4):
            return self._decision(
                "down",
                "Auto: continue stepping toward Oak Lab's exit once the rival handoff starts yielding movement",
            )

        return None

    def _is_opening_party(self, memory: Dict[str, Any]) -> bool:
        """Keep the controller scoped to the fresh-starter opening sequence."""
        if int(memory.get("badge_count", 0) or 0) != 0:
            return False

        party = memory.get("party", []) or []
        if len(party) != 1:
            return False

        starter = party[0] or {}
        level = int(starter.get("level", 0) or 0)
        moves = starter.get("moves", []) or []
        return level == 5 and len(moves) <= 2

    def _decision(self, action: str, reasoning: str) -> Dict[str, Any]:
        """Build a deterministic control-layer decision payload."""
        return {
            "action": action,
            "reasoning": reasoning,
            "goal_update": None,
            "recorded_in_context": False,
        }
