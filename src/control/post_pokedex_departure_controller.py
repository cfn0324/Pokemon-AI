"""Deterministic helper for leaving Oak's Lab and heading back to Viridian after the Pokedex scene."""

from __future__ import annotations

from typing import Any, Dict, Optional


class PostPokedexDepartureController:
    """Handle the fragile first departure after Oak finishes the parcel/Pokedex scene."""

    PALLET_TOWN_MAP_ID = 0
    VIRIDIAN_CITY_MAP_ID = 1
    ROUTE_2_MAP_ID = 13
    ROUTE_1_MAP_ID = 12
    OAKS_LAB_MAP_ID = 40
    VIRIDIAN_FOREST_SOUTH_GATE_MAP_ID = 50
    VIRIDIAN_FOREST_MAP_ID = 51
    EVENT_GOT_POKEDEX = "got_pokedex"

    def __init__(self) -> None:
        self._active = False
        self._completed = False

    def reset(self) -> None:
        """Forget any in-progress post-Pokedex departure state."""
        self._active = False
        self._completed = False

    def maybe_decide(
        self,
        current_state: Dict[str, Any],
        screen_type: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Return deterministic actions for the first post-Pokedex departure."""
        memory = current_state.get("memory", {}) or {}
        position = memory.get("position", {}) or {}
        events = memory.get("events", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        map_id_raw = position.get("map_id", -1)
        x_raw = position.get("x", -1)
        y_raw = position.get("y", -1)
        map_id = int(-1 if map_id_raw is None else map_id_raw)
        x = int(-1 if x_raw is None else x_raw)
        y = int(-1 if y_raw is None else y_raw)
        got_pokedex = bool(events.get(self.EVENT_GOT_POKEDEX))
        normalized_screen = (screen_type or "").strip().lower()

        if self._completed:
            if self._should_resume_after_blackout(memory, map_id, x, y, got_pokedex):
                self._completed = False
            else:
                return None

        if self._active and map_id == self.VIRIDIAN_FOREST_MAP_ID and got_pokedex:
            self._completed = True
            self._active = False
            return None

        if self._active:
            if not self._can_continue(memory, map_id, got_pokedex):
                self.reset()
                return None
        elif not self._should_start(memory, map_id, x, y, got_pokedex):
            return None
        else:
            self._active = True

        if memory.get("in_battle"):
            return None

        if (
            map_id == self.OAKS_LAB_MAP_ID
            and normalized_screen in {"dialogue", "battle"}
            and ui_state.get("text_box_active")
        ):
            return self._decision(
                "a",
                "Auto: finish any lingering post-Pokedex dialogue before leaving Oak's Lab",
            )

        if map_id == self.OAKS_LAB_MAP_ID:
            decision = self._oaks_lab_exit_decision(x, y)
            if decision:
                return decision
            return None

        if map_id == self.PALLET_TOWN_MAP_ID:
            decision = self._pallet_route_decision(x, y)
            if decision:
                return decision
            return None

        if map_id == self.ROUTE_1_MAP_ID:
            decision = self._route1_decision(x, y)
            if decision:
                return decision
            return None

        if map_id == self.VIRIDIAN_CITY_MAP_ID:
            decision = self._viridian_northbound_decision(x, y)
            if decision:
                return decision
            self.reset()
            return None

        if map_id == self.ROUTE_2_MAP_ID:
            decision = self._route2_south_decision(x, y)
            if decision:
                return decision
            self.reset()
            return None

        if map_id == self.VIRIDIAN_FOREST_SOUTH_GATE_MAP_ID:
            decision = self._viridian_forest_south_gate_decision(x, y)
            if decision:
                return decision
            self.reset()
            return None

        return None

    def is_guided_state(self, current_state: Dict[str, Any]) -> bool:
        """Return whether this controller should still own the current state."""
        memory = current_state.get("memory", {}) or {}
        position = memory.get("position", {}) or {}
        events = memory.get("events", {}) or {}
        map_id_raw = position.get("map_id", -1)
        x_raw = position.get("x", -1)
        y_raw = position.get("y", -1)
        map_id = int(-1 if map_id_raw is None else map_id_raw)
        x = int(-1 if x_raw is None else x_raw)
        y = int(-1 if y_raw is None else y_raw)
        got_pokedex = bool(events.get(self.EVENT_GOT_POKEDEX))

        if self._completed:
            return False
        if self._active:
            return self._can_continue(memory, map_id, got_pokedex)
        return self._should_start(memory, map_id, x, y, got_pokedex)

    def _should_start(
        self,
        memory: Dict[str, Any],
        map_id: int,
        x: int,
        y: int,
        got_pokedex: bool,
    ) -> bool:
        if not self._can_continue(memory, map_id, got_pokedex):
            return False

        if map_id == self.OAKS_LAB_MAP_ID and 3 <= y <= 11 and 4 <= x <= 5:
            return True

        if map_id == self.PALLET_TOWN_MAP_ID and self._pallet_route_decision(x, y):
            return True

        if map_id == self.ROUTE_1_MAP_ID and self._route1_decision(x, y):
            return True

        if map_id == self.VIRIDIAN_CITY_MAP_ID and self._viridian_northbound_decision(x, y):
            return True

        if map_id == self.ROUTE_2_MAP_ID and self._route2_south_decision(x, y):
            return True

        if (
            map_id == self.VIRIDIAN_FOREST_SOUTH_GATE_MAP_ID
            and self._viridian_forest_south_gate_decision(x, y)
        ):
            return True

        return False

    def _can_continue(self, memory: Dict[str, Any], map_id: int, got_pokedex: bool) -> bool:
        if not got_pokedex:
            return False
        if map_id not in {
            self.OAKS_LAB_MAP_ID,
            self.PALLET_TOWN_MAP_ID,
            self.ROUTE_1_MAP_ID,
            self.VIRIDIAN_CITY_MAP_ID,
            self.ROUTE_2_MAP_ID,
            self.VIRIDIAN_FOREST_SOUTH_GATE_MAP_ID,
        }:
            return False
        if int(memory.get("badge_count", 0) or 0) != 0:
            return False
        if int(memory.get("item_count", 0) or 0) != 0:
            return False

        party = memory.get("party", []) or []
        if len(party) != 1:
            return False

        starter = party[0] or {}
        return int(starter.get("level", 0) or 0) >= 6

    def _oaks_lab_exit_decision(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        if y < 11:
            if x < 4:
                return self._decision(
                    "right",
                    "Auto: realign with Oak's Lab center aisle before leaving after the Pokedex scene",
                )
            if x > 5:
                return self._decision(
                    "left",
                    "Auto: move back toward Oak's Lab center aisle before heading outside",
                )
            if x > 4 and y <= 3:
                return self._decision(
                    "left",
                    "Auto: sidestep off Oak's counter lane so the exit path stays clear",
                )
            return self._decision(
                "down",
                "Auto: walk back down Oak's Lab aisle toward the exit",
            )
        if y == 11 and x in {4, 5}:
            return self._decision(
                "down",
                "Auto: step through Oak's Lab exit warp and resume the journey",
            )
        return None

    def _pallet_route_decision(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        if x == 5 and 6 <= y < 8:
            return self._decision(
                "down",
                "Auto: step out from the player's house doorstep after an early blackout so the northbound route can resume",
            )
        if y == 8 and 5 <= x < 8:
            return self._decision(
                "right",
                "Auto: recover from the player's house side lane by rejoining Pallet Town's main northbound path",
            )
        if x == 8 and 3 < y <= 8:
            return self._decision(
                "up",
                "Auto: climb Pallet Town's west-side lane back toward the Route 1 approach after a blackout recovery",
            )
        if y == 3 and 8 <= x < 11:
            return self._decision(
                "right",
                "Auto: cross Pallet Town's upper lane back to the Route 1 gate after recovering at home",
            )
        if x == 11 and 0 < y <= 3:
            return self._decision(
                "up",
                "Auto: resume the Route 1 departure from Pallet Town after the blackout recovery path",
            )
        if y <= 2:
            if 0 < y <= 2 and x < 11:
                return self._decision(
                    "right",
                    "Auto: keep sliding right along Pallet Town's north edge until the Route 1 exit opening lines up",
                )
            if x > 11:
                return self._decision(
                    "left",
                    "Auto: line up with Pallet Town's north exit opening after receiving the Pokedex",
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
                "Auto: follow Pallet Town's east path north toward Route 1",
            )
        if x < 16 and y >= 12:
            return self._decision(
                "right",
                "Auto: route around Oak's Lab fence onto Pallet Town's east path",
            )
        if y < 12:
            return self._decision(
                "down",
                "Auto: step south from Oak's Lab doorstep to rejoin Pallet Town's northbound route",
            )
        return None

    def _should_resume_after_blackout(
        self,
        memory: Dict[str, Any],
        map_id: int,
        x: int,
        y: int,
        got_pokedex: bool,
    ) -> bool:
        """Allow the controller to resume if the pre-badge run blacks out after reaching the forest."""
        if map_id == self.VIRIDIAN_FOREST_MAP_ID:
            return False
        return self._should_start(memory, map_id, x, y, got_pokedex)

    def _route1_decision(self, x: int, y: int) -> Optional[Dict[str, Any]]:
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

    def _viridian_northbound_decision(self, x: int, y: int) -> Optional[Dict[str, Any]]:
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
        if x == 19 and 2 < y <= 27:
            return self._decision(
                "up",
                "Auto: keep following Viridian City's main north road toward Route 2",
            )
        if (x, y) == (19, 2):
            return self._decision(
                "left",
                "Auto: sidestep Viridian City's north trainer tips sign before exiting to Route 2",
            )
        if x == 18 and 0 < y <= 2:
            return self._decision(
                "up",
                "Auto: finish the Viridian City north-exit lane after clearing the sign",
            )
        if (x, y) == (18, 0):
            return self._decision(
                "up",
                "Auto: cross Viridian City's north boundary into Route 2",
            )
        return None

    def _route2_south_decision(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        if x in {8, 9} and 62 < y <= 71:
            return self._decision(
                "up",
                "Auto: climb Route 2's south corridor away from the Viridian return warp",
            )
        if y == 62 and x in {8, 9}:
            return self._decision(
                "left",
                "Auto: step west off Route 2's south corridor before the forest approach bend",
            )
        if y == 62 and 3 <= x < 7:
            return self._decision(
                "right",
                "Auto: recover from Route 2's west dead-end and head back toward the real forest approach",
            )
        if x == 7 and 57 < y <= 62:
            return self._decision(
                "up",
                "Auto: climb Route 2's inner northbound lane toward the forest detour",
            )
        if y == 57 and 5 < x <= 7:
            return self._decision(
                "left",
                "Auto: cut west across Route 2's mid-lane opening toward the upper corridor",
            )
        if (x, y) == (5, 57):
            return self._decision(
                "up",
                "Auto: step into Route 2's upper-west corridor after the mid-lane turn",
            )
        if (x, y) == (5, 56):
            return self._decision(
                "left",
                "Auto: finish the Route 2 mid-lane jog before the long north climb",
            )
        if x == 4 and 48 < y <= 56:
            return self._decision(
                "up",
                "Auto: follow Route 2's upper-west corridor north toward the final bend",
            )
        if y == 48 and 4 <= x < 9:
            return self._decision(
                "right",
                "Auto: cross Route 2's upper connector toward the forest gate column",
            )
        if x == 9 and 44 < y <= 48:
            return self._decision(
                "up",
                "Auto: climb Route 2's final northbound column beside the forest gate",
            )
        if y == 44 and 3 < x <= 9:
            return self._decision(
                "left",
                "Auto: line up with Viridian Forest's south gate entrance tile",
            )
        if (x, y) in {(3, 43), (3, 44)}:
            return self._decision(
                "up",
                "Auto: step into Viridian Forest's south gate from Route 2",
            )
        return None

    def _viridian_forest_south_gate_decision(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        if x < 4 and 0 <= y <= 7:
            return self._decision(
                "right",
                "Auto: realign inside Viridian Forest's south gate with the northbound doorway lane",
            )
        if x > 5 and 0 <= y <= 7:
            return self._decision(
                "left",
                "Auto: move back to Viridian Forest's south gate center aisle before exiting north",
            )
        if (x, y) == (4, 1):
            return self._decision(
                "right",
                "Auto: sidestep onto Viridian Forest's active north exit tile before leaving the gate",
            )
        if x in {4, 5} and 1 < y <= 7:
            return self._decision(
                "up",
                "Auto: walk straight through Viridian Forest's south gate into the forest entrance",
            )
        if (x, y) == (5, 1):
            return self._decision(
                "up",
                "Auto: step out of Viridian Forest's south gate and into the forest clearing",
            )
        return None

    def _decision(self, action: str, reasoning: str) -> Dict[str, Any]:
        return {
            "action": action,
            "reasoning": reasoning,
            "goal_update": None,
            "recorded_in_context": False,
        }
