"""Deterministic helper for the first Oak Lab rival battle."""

from __future__ import annotations

from typing import Any, Dict, Optional


class OakLabRivalBattleController:
    """Drive the mandatory first rival interaction without the LLM."""

    def __init__(self) -> None:
        self._active = False
        self._battle_seen = False

    def reset(self) -> None:
        """Forget any in-progress Oak-lab rival sequence."""
        self._active = False
        self._battle_seen = False

    def maybe_decide(
        self,
        current_state: Dict[str, Any],
        screen_type: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Return deterministic Oak-lab rival actions when in the opening sequence."""
        memory = current_state.get("memory", {}) or {}
        position = memory.get("position", {}) or {}
        battle = memory.get("battle", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        map_id = int(position.get("map_id", -1) or -1)
        x = int(position.get("x", -1) or -1)
        y = int(position.get("y", -1) or -1)
        direction = str(memory.get("direction") or "").strip().lower()
        enemy_hp_raw = battle.get("enemy_current_hp")
        enemy_hp = None if enemy_hp_raw is None else int(enemy_hp_raw)

        if map_id != 40:
            self.reset()
            return None

        if self._active:
            if not self._can_continue_sequence(memory):
                self.reset()
                return None
        elif not self._is_opening_party(memory):
            self.reset()
            return None

        in_battle = bool(memory.get("in_battle"))
        if not self._active:
            if in_battle:
                self._active = True
                self._battle_seen = True
            elif (x, y) == (5, 5):
                self._active = True
            elif (x, y) == (5, 6) and direction == "up":
                self._active = True
            else:
                return None

        if in_battle:
            self._battle_seen = True
            if enemy_hp is not None and enemy_hp <= 0 and ui_state.get("menu_active"):
                return {
                    "action": "b",
                    "reasoning": "Auto: close Oak Lab's post-faint battle menu before finishing the remaining victory dialogue",
                    "goal_update": None,
                    "recorded_in_context": False,
                }
            return {
                "action": "a",
                "reasoning": "Auto: fast-advance the first Oak Lab rival battle and confirm the default opening move",
                "goal_update": None,
                "recorded_in_context": False,
            }

        if self._battle_seen:
            self.reset()
            return None

        normalized_screen = (screen_type or "").strip().lower()
        if (x, y) == (5, 5):
            return {
                "action": "down",
                "reasoning": "Auto: step toward Oak Lab's exit to trigger the mandatory first rival battle",
                "goal_update": None,
                "recorded_in_context": False,
            }

        if (x, y) == (5, 6) and direction == "up":
            return {
                "action": "a",
                "reasoning": "Auto: advance Oak Lab's mandatory rival challenge until the battle fully starts",
                "goal_update": None,
                "recorded_in_context": False,
            }

        if normalized_screen == "battle":
            return {
                "action": "a",
                "reasoning": "Auto: keep the first Oak Lab rival sequence moving while the battle scene finishes loading",
                "goal_update": None,
                "recorded_in_context": False,
            }

        self.reset()
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

    def _can_continue_sequence(self, memory: Dict[str, Any]) -> bool:
        """Allow the active opener to finish even if the starter levels up mid-battle."""
        if int(memory.get("badge_count", 0) or 0) != 0:
            return False
        return len(memory.get("party", []) or []) == 1
