"""Deterministic helper for early solo-starter battles before the first badge."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class EarlyBattleController:
    """Keep early-game battles progressing without depending on the LLM."""

    _STALL_RECOVERY_THRESHOLD = 12
    _LOW_PRIORITY_MOVE_IDS = {39, 45}

    def __init__(self) -> None:
        self._recovery_actions: List[str] = []
        self._recovery_reasoning: Optional[str] = None

    def reset(self) -> None:
        """Controllers share a reset hook even when no local state is tracked."""
        self._recovery_actions = []
        self._recovery_reasoning = None
        return None

    def maybe_decide(
        self,
        current_state: Dict[str, Any],
        screen_type: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Return safe deterministic inputs for early mandatory battles."""
        memory = current_state.get("memory", {}) or {}
        if not self._should_control(memory):
            return None

        battle = memory.get("battle", {}) or {}
        battle_summary = current_state.get("battle_summary", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        normalized_screen = (screen_type or "").strip().lower()
        enemy_hp_raw = battle.get("enemy_current_hp")
        enemy_hp = None if enemy_hp_raw is None else int(enemy_hp_raw)

        if ui_state.get("menu_active") and enemy_hp is not None and enemy_hp <= 0:
            return {
                "action": "b",
                "reasoning": "Auto: close the stale early-battle menu after the enemy faints so victory text can continue",
                "goal_update": None,
                "recorded_in_context": False,
            }

        if ui_state.get("text_box_active"):
            self._clear_recovery_script()
            return {
                "action": "a",
                "reasoning": "Auto: keep advancing early-battle text even if RAM still reports a stale menu overlay",
                "goal_update": None,
                "recorded_in_context": False,
            }

        recovery_decision = self._get_recovery_decision(current_state, battle_summary, enemy_hp)
        if recovery_decision:
            return recovery_decision

        if ui_state.get("menu_active"):
            self._clear_recovery_script()
            return {
                "action": "a",
                "reasoning": "Auto: accept the default early-battle menu choice so the fight keeps moving",
                "goal_update": None,
                "recorded_in_context": False,
            }

        if normalized_screen == "battle":
            self._clear_recovery_script()
            return {
                "action": "a",
                "reasoning": "Auto: advance the active early-battle text until the next menu or result appears",
                "goal_update": None,
                "recorded_in_context": False,
            }

        self._clear_recovery_script()
        return {
            "action": "a",
            "reasoning": "Auto: keep the early battle progressing instead of spending a turn on model inference",
            "goal_update": None,
            "recorded_in_context": False,
        }

    def _should_control(self, memory: Dict[str, Any]) -> bool:
        """Scope the controller to the fragile no-badge solo-starter phase."""
        if not memory.get("in_battle"):
            return False
        if int(memory.get("badge_count", 0) or 0) != 0:
            return False

        party = memory.get("party", []) or []
        if len(party) != 1:
            return False
        return True

    def _get_recovery_decision(
        self,
        current_state: Dict[str, Any],
        battle_summary: Dict[str, Any],
        enemy_hp: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        """Break out of stalled move-selection deadlocks once the default move becomes unusable."""
        if enemy_hp is not None and enemy_hp <= 0:
            self._clear_recovery_script()
            return None

        ui_state = ((current_state.get("memory", {}) or {}).get("ui", {}) or {})
        if ui_state.get("text_box_active"):
            self._clear_recovery_script()
            return None

        if self._recovery_actions:
            return self._consume_recovery_action()

        stall_turns = self._safe_int(battle_summary.get("battle_stall_turns"))
        if stall_turns < self._STALL_RECOVERY_THRESHOLD:
            return None

        target_slot = self._get_stalled_move_target_slot(current_state)
        if target_slot is None:
            return None

        self._recovery_actions = self._build_move_recovery_script(target_slot)
        self._recovery_reasoning = (
            "Auto: battle progress stalled after the default move became unusable, so back out "
            f"and reselect move slot {target_slot}"
        )
        return self._consume_recovery_action()

    def _consume_recovery_action(self) -> Dict[str, Any]:
        """Return the next queued recovery input for a stalled early battle."""
        action = self._recovery_actions.pop(0)
        return {
            "action": action,
            "reasoning": self._recovery_reasoning,
            "goal_update": None,
            "recorded_in_context": False,
        }

    def _clear_recovery_script(self) -> None:
        """Forget any queued recovery inputs once the battle visibly progresses."""
        self._recovery_actions = []
        self._recovery_reasoning = None

    def _get_stalled_move_target_slot(self, current_state: Dict[str, Any]) -> Optional[int]:
        """Pick a better move slot when the default slot appears exhausted."""
        memory = current_state.get("memory", {}) or {}
        party = memory.get("party", []) or []
        if not party:
            return None

        moves = (party[0] or {}).get("moves", []) or []
        if not moves:
            return None

        default_pp = self._safe_int((moves[0] or {}).get("pp"))
        if default_pp > 0:
            return None

        preferred_slots: List[int] = []
        fallback_slots: List[int] = []
        for slot_index, move in enumerate(moves[1:], start=2):
            pp = self._safe_int((move or {}).get("pp"))
            if pp <= 0:
                continue
            move_id = self._safe_int((move or {}).get("move_id"))
            if move_id in self._LOW_PRIORITY_MOVE_IDS:
                fallback_slots.append(slot_index)
            else:
                preferred_slots.append(slot_index)

        if preferred_slots:
            return preferred_slots[0]
        if fallback_slots:
            return fallback_slots[0]
        return None

    def _build_move_recovery_script(self, slot_index: int) -> List[str]:
        """Build a short button sequence that reopens the move menu on a usable move slot."""
        move_cursor_paths = {
            1: ["up", "left", "a"],
            2: ["up", "right", "a"],
            3: ["left", "down", "a"],
            4: ["right", "down", "a"],
        }
        return ["b", "up", "left", "a", *move_cursor_paths.get(slot_index, ["left", "down", "a"])]

    @staticmethod
    def _safe_int(value: Any) -> int:
        """Best-effort integer normalization for RAM-backed counters."""
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
