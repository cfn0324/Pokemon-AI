"""Deterministic helper for the fixed post-rival route through Viridian's south gate."""

from __future__ import annotations

from typing import Any, Dict, Optional


class PostBattleIntroRouteController:
    """Handle the fixed path from the first rival battle through Route 1 into Viridian."""

    def __init__(self) -> None:
        self._active = False

    def reset(self) -> None:
        """Forget any in-progress post-battle intro routing."""
        self._active = False

    def maybe_decide(
        self,
        current_state: Dict[str, Any],
        screen_type: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Return deterministic post-battle actions when the early-game route is fixed."""
        memory = current_state.get("memory", {}) or {}
        position = memory.get("position", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        map_id_raw = position.get("map_id", -1)
        x_raw = position.get("x", -1)
        y_raw = position.get("y", -1)
        map_id = int(-1 if map_id_raw is None else map_id_raw)
        x = int(-1 if x_raw is None else x_raw)
        y = int(-1 if y_raw is None else y_raw)
        normalized_screen = (screen_type or "").strip().lower()

        if self._active:
            if not self._can_continue(memory, map_id):
                self.reset()
                return None
        elif not self._should_start(memory, map_id, x, y):
            return None
        else:
            self._active = True

        if normalized_screen in {"dialogue", "battle"} and ui_state.get("text_box_active"):
            return {
                "action": "a",
                "reasoning": "Auto: finish the fixed post-battle intro dialogue before walking toward Route 1",
                "goal_update": None,
                "recorded_in_context": False,
            }

        if map_id == 40:
            return self._decision(
                "down",
                "Auto: leave Oak's Lab after the first rival battle",
            )

        if map_id == 0:
            if y <= 2:
                if x > 11:
                    return self._decision(
                        "left",
                        "Auto: line up with Pallet Town's north exit opening",
                    )
                if y > 0:
                    return self._decision(
                        "up",
                        "Auto: step through Pallet Town's north grass opening toward Route 1",
                    )
                if x == 11 and y == 0:
                    return self._decision(
                        "up",
                        "Auto: cross the north boundary into Route 1",
                    )
            if x >= 16 and y > 2:
                return self._decision(
                    "up",
                    "Auto: follow Pallet Town's east path north toward the Route 1 gate grass",
                )
            if x < 16 and y >= 12:
                return self._decision(
                    "right",
                    "Auto: route around Oak's Lab fence onto Pallet Town's east path",
                )
            if y < 12:
                return self._decision(
                    "down",
                    "Auto: head south from Oak's Lab toward the fixed Pallet Town route",
                )

        if map_id == 12:
            route1_decision = self._route1_decision(x, y)
            if route1_decision:
                return route1_decision

        if map_id == 1:
            viridian_decision = self._viridian_south_gate_decision(x, y)
            if viridian_decision:
                return viridian_decision

        self.reset()
        return None

    def _should_start(
        self,
        memory: Dict[str, Any],
        map_id: int,
        x: int,
        y: int,
    ) -> bool:
        """Only trigger after the first rival battle has clearly completed."""
        if not self._can_continue(memory, map_id):
            return False

        if map_id == 40 and (x, y) == (5, 6):
            return True

        if map_id == 0 and (
            (10 <= x <= 16 and 12 <= y <= 13)
            or (x >= 16 and 2 <= y <= 13)
            or (11 <= x <= 16 and 0 <= y <= 2)
        ):
            return True

        if map_id == 12 and self._route1_decision(x, y):
            return True

        return False

    def _can_continue(self, memory: Dict[str, Any], map_id: int) -> bool:
        """Keep the controller narrowly scoped to the very early post-battle route."""
        if map_id not in {0, 1, 12, 40}:
            return False
        if memory.get("in_battle"):
            return False
        if int(memory.get("badge_count", 0) or 0) != 0:
            return False
        if int(memory.get("money", 0) or 0) < 3175:
            return False
        if int(memory.get("item_count", 0) or 0) != 0:
            return False

        party = memory.get("party", []) or []
        if len(party) != 1:
            return False

        starter = party[0] or {}
        return int(starter.get("level", 0) or 0) >= 6

    def _route1_decision(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        """Return the narrow deterministic Route 1 route into Viridian City."""
        if x == 11 and y >= 34:
            return self._decision(
                "up",
                "Auto: leave Route 1's south entrance tile and start the northbound walk",
            )
        if x == 11 and y == 33:
            return self._decision(
                "left",
                "Auto: shift into Route 1's left-side corridor around the first hedge",
            )
        if x == 10 and 28 < y <= 33:
            return self._decision(
                "up",
                "Auto: follow Route 1's lower-left corridor north",
            )
        if y == 28 and 8 < x <= 11:
            return self._decision(
                "left",
                "Auto: keep sliding left along Route 1 until the north path opens",
            )
        if x == 8 and 26 < y <= 28:
            return self._decision(
                "up",
                "Auto: climb through Route 1's first opening",
            )
        if y == 26 and 8 <= x < 10:
            return self._decision(
                "right",
                "Auto: cut right across Route 1's mid-route ledge opening",
            )
        if x == 10 and 24 < y <= 26:
            return self._decision(
                "up",
                "Auto: advance to Route 1's mid-route bend",
            )
        if (x, y) == (10, 24):
            return self._decision(
                "right",
                "Auto: enter the small Route 1 dogleg around the central hedge",
            )
        if (x, y) == (11, 24):
            return self._decision(
                "down",
                "Auto: dip one tile to line up with Route 1's right-side passage",
            )
        if (x, y) == (11, 25):
            return self._decision(
                "right",
                "Auto: step into Route 1's right-side lane",
            )
        if x == 12 and 20 < y <= 25:
            return self._decision(
                "up",
                "Auto: continue north up Route 1's right-side lane",
            )
        if y == 20 and 9 < x <= 12:
            return self._decision(
                "left",
                "Auto: cut back left across Route 1's upper corridor",
            )
        if x == 9 and 14 < y <= 20:
            return self._decision(
                "up",
                "Auto: climb Route 1's upper-left corridor toward Viridian",
            )
        if y == 14 and 9 <= x < 15:
            return self._decision(
                "right",
                "Auto: cross Route 1's top corridor to the Viridian gate lane",
            )
        if x == 15 and 2 < y <= 14:
            return self._decision(
                "up",
                "Auto: follow Route 1's final straight north toward Viridian",
            )
        if y == 2 and 11 < x <= 15:
            return self._decision(
                "left",
                "Auto: align with Viridian City's south gate opening",
            )
        if x == 11 and y <= 2:
            return self._decision(
                "up",
                "Auto: step through Route 1's north exit into Viridian City",
            )
        return None

    def _viridian_south_gate_decision(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        """Guide the first few Viridian tiles past the south gate sign choke point."""
        if x == 21 and 30 < y <= 35:
            return self._decision(
                "up",
                "Auto: continue north from Viridian City's south gate toward the central path",
            )
        if (x, y) == (21, 30):
            return self._decision(
                "left",
                "Auto: sidestep Viridian City's south sign so the north path stays clear",
            )
        if x == 20 and 28 < y <= 30:
            return self._decision(
                "up",
                "Auto: move up Viridian City's south approach after clearing the sign",
            )
        if (x, y) == (20, 28):
            return self._decision(
                "left",
                "Auto: align with the opening in Viridian City's upper hedge row",
            )
        if (x, y) == (19, 28):
            return self._decision(
                "up",
                "Auto: step through Viridian City's hedge opening onto the northbound path",
            )
        return None

    def _decision(self, action: str, reasoning: str) -> Dict[str, Any]:
        """Build a deterministic control-layer decision payload."""
        return {
            "action": action,
            "reasoning": reasoning,
            "goal_update": None,
            "recorded_in_context": False,
        }
