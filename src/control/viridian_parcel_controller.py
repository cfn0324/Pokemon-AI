"""Deterministic helper for Viridian City's first mart parcel errand."""

from __future__ import annotations

from typing import Any, Dict, Optional


class ViridianParcelController:
    """Handle the first Viridian City parcel trip before broader exploration is needed."""

    PALLET_TOWN_MAP_ID = 0
    VIRIDIAN_CITY_MAP_ID = 1
    ROUTE_1_MAP_ID = 12
    OAKS_LAB_MAP_ID = 40
    VIRIDIAN_MART_MAP_ID = 42  # pret/pokered: VIRIDIAN_MART = $2A
    EVENT_GOT_POKEDEX = "got_pokedex"
    EVENT_OAK_GOT_PARCEL = "oak_got_parcel"
    EVENT_GOT_OAKS_PARCEL = "got_oaks_parcel"

    def __init__(self) -> None:
        self._active = False
        self._returning = False
        self._completed = False

    def reset(self) -> None:
        """Forget any in-progress Viridian parcel sequence."""
        self._active = False
        self._returning = False
        self._completed = False

    def _deactivate(self) -> None:
        """Drop the current route state without marking the parcel arc complete."""
        self._active = False
        self._returning = False

    def maybe_decide(
        self,
        current_state: Dict[str, Any],
        screen_type: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Return deterministic Viridian actions for the first parcel errand."""
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
        item_count = int(memory.get("item_count", 0) or 0)
        got_pokedex = bool(events.get(self.EVENT_GOT_POKEDEX))
        oak_got_parcel = bool(events.get(self.EVENT_OAK_GOT_PARCEL))
        got_oaks_parcel = bool(events.get(self.EVENT_GOT_OAKS_PARCEL))
        normalized_screen = (screen_type or "").strip().lower()
        text_box_active = bool(ui_state.get("text_box_active"))

        if got_pokedex or oak_got_parcel:
            self._completed = True
            self._deactivate()
            return None

        if self._completed:
            return None

        if item_count > 0 or got_oaks_parcel:
            self._returning = True

        if self._active:
            if not self._can_continue(memory, map_id):
                self._deactivate()
                return None
        elif not self._should_start(memory, map_id, x, y, item_count, got_oaks_parcel):
            return None
        else:
            self._active = True

        if memory.get("in_battle"):
            return None

        if normalized_screen in {"dialogue", "battle"} and text_box_active:
            return self._decision(
                "a",
                "Auto: finish the mandatory Viridian parcel dialogue before resuming movement",
            )

        if map_id == self.VIRIDIAN_MART_MAP_ID:
            mart_decision = self._mart_decision(x, y, item_count, ui_state, normalized_screen)
            if mart_decision:
                return mart_decision
            return None

        if not self._returning:
            if map_id != self.VIRIDIAN_CITY_MAP_ID:
                self._deactivate()
                return None
            outbound = self._route_to_mart(x, y)
            if outbound:
                return outbound
        else:
            inbound = self._return_route_decision(map_id, x, y, item_count, normalized_screen)
            if inbound:
                return inbound

        return None

    def is_guided_state(self, current_state: Dict[str, Any]) -> bool:
        """Return whether the parcel controller should still own this state."""
        memory = current_state.get("memory", {}) or {}
        position = memory.get("position", {}) or {}
        events = memory.get("events", {}) or {}
        map_id_raw = position.get("map_id", -1)
        x_raw = position.get("x", -1)
        y_raw = position.get("y", -1)
        map_id = int(-1 if map_id_raw is None else map_id_raw)
        x = int(-1 if x_raw is None else x_raw)
        y = int(-1 if y_raw is None else y_raw)
        item_count = int(memory.get("item_count", 0) or 0)
        got_pokedex = bool(events.get(self.EVENT_GOT_POKEDEX))
        oak_got_parcel = bool(events.get(self.EVENT_OAK_GOT_PARCEL))
        got_oaks_parcel = bool(events.get(self.EVENT_GOT_OAKS_PARCEL))

        if self._completed or got_pokedex or oak_got_parcel:
            return False
        if self._active:
            return self._can_continue(memory, map_id)
        return self._should_start(memory, map_id, x, y, item_count, got_oaks_parcel)

    def _should_start(
        self,
        memory: Dict[str, Any],
        map_id: int,
        x: int,
        y: int,
        item_count: int,
        got_oaks_parcel: bool,
    ) -> bool:
        """Only trigger during the fragile first Viridian visit before Brock."""
        if not self._base_scope_matches(memory):
            return False

        if (item_count > 0 or got_oaks_parcel) and map_id in {
            self.VIRIDIAN_CITY_MAP_ID,
            self.VIRIDIAN_MART_MAP_ID,
            self.ROUTE_1_MAP_ID,
            self.PALLET_TOWN_MAP_ID,
            self.OAKS_LAB_MAP_ID,
        }:
            return True

        if map_id == self.VIRIDIAN_MART_MAP_ID:
            return True

        if map_id != self.VIRIDIAN_CITY_MAP_ID:
            return False

        return 19 <= x <= 29 and 14 <= y <= 35

    def _can_continue(self, memory: Dict[str, Any], map_id: int) -> bool:
        """Keep the controller limited to the early solo-starter parcel trip."""
        if map_id not in {
            self.VIRIDIAN_CITY_MAP_ID,
            self.VIRIDIAN_MART_MAP_ID,
            self.ROUTE_1_MAP_ID,
            self.PALLET_TOWN_MAP_ID,
            self.OAKS_LAB_MAP_ID,
        }:
            return False
        return self._base_scope_matches(memory)

    def _base_scope_matches(self, memory: Dict[str, Any]) -> bool:
        if int(memory.get("badge_count", 0) or 0) != 0:
            return False

        party = memory.get("party", []) or []
        if len(party) != 1:
            return False

        starter = party[0] or {}
        level = int(starter.get("level", 0) or 0)
        return 6 <= level <= 10

    def _route_to_mart(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        """Guide the first trip from Viridian's south path to the Pokemart door."""
        if x == 19 and 16 < y <= 27:
            return self._decision(
                "up",
                "Auto: keep climbing Viridian City's main path until the mart turnoff",
            )
        if x == 19 and 14 <= y < 16:
            return self._decision(
                "down",
                "Auto: drop back to Viridian City's eastbound mart corridor",
            )
        if y == 16 and 19 <= x < 27:
            return self._decision(
                "right",
                "Auto: follow Viridian City's upper road east toward the Pokemart entrance",
            )
        if x == 27 and 16 <= y < 20:
            return self._decision(
                "down",
                "Auto: bend south around Viridian City's blocked hedge toward the Pokemart lane",
            )
        if y == 20 and 27 <= x < 29:
            return self._decision(
                "right",
                "Auto: cross Viridian City's lower east lane toward the Pokemart door",
            )
        if x == 29 and y == 20:
            return self._decision(
                "up",
                "Auto: step up onto Viridian Mart's doorway tile",
            )
        return None

    def _return_route_decision(
        self,
        map_id: int,
        x: int,
        y: int,
        item_count: int,
        screen_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Continue the parcel return through Route 1, Pallet Town, and Oak's Lab."""
        if map_id == self.VIRIDIAN_CITY_MAP_ID:
            return self._route_back_to_south_exit(x, y)
        if map_id == self.ROUTE_1_MAP_ID:
            return self._route1_return_decision(x, y)
        if map_id == self.PALLET_TOWN_MAP_ID:
            return self._pallet_return_decision(x, y)
        if map_id == self.OAKS_LAB_MAP_ID:
            return self._oaks_lab_return_decision(x, y, item_count, screen_type)
        return None

    def _mart_decision(
        self,
        x: int,
        y: int,
        item_count: int,
        ui_state: Dict[str, Any],
        screen_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Handle Viridian Mart's scripted parcel handoff and simple exit path."""
        if ui_state.get("text_box_active") or screen_type == "dialogue":
            return self._decision(
                "a",
                "Auto: advance Viridian Mart's parcel handoff dialogue",
            )

        if item_count == 0:
            return {
                "action": "wait",
                "reasoning": "Auto: let Viridian Mart's clerk script start before confirming the parcel dialogue",
                "goal_update": None,
                "recorded_in_context": False,
                "allow_wait": True,
            }

        if x < 3:
            return self._decision(
                "right",
                "Auto: line up with Viridian Mart's exit warp after receiving Oak's Parcel",
            )
        if y < 7:
            return self._decision(
                "down",
                "Auto: walk back to Viridian Mart's exit after receiving Oak's Parcel",
            )
        return None

    def _route_back_to_south_exit(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        """Guide the first return from Viridian Mart back to the south route exit."""
        if x == 29 and y == 19:
            return self._decision(
                "down",
                "Auto: step back off Viridian Mart's doorway tile before heading south",
            )
        if y == 20 and 19 < x <= 29:
            return self._decision(
                "left",
                "Auto: retrace Viridian City's lower east lane back toward the main road",
            )
        if x == 19 and 20 <= y < 28:
            return self._decision(
                "down",
                "Auto: descend Viridian City's central road toward the south exit",
            )
        if x == 19 and y == 28:
            return self._decision(
                "right",
                "Auto: realign with Viridian City's south gate opening",
            )
        if x == 20 and 28 <= y < 30:
            return self._decision(
                "down",
                "Auto: continue through Viridian City's south approach",
            )
        if x == 20 and y == 30:
            return self._decision(
                "right",
                "Auto: step back into Viridian City's south exit lane",
            )
        if x == 21 and 30 <= y <= 35:
            return self._decision(
                "down",
                "Auto: head back through Viridian City's south exit to return Oak's Parcel",
            )
        return None

    def _route1_return_decision(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        """Guide the Route 1 return from Viridian back into Pallet Town."""
        if x == 11 and 0 <= y < 3:
            return self._decision(
                "down",
                "Auto: continue south from Viridian's gate until Route 1 opens into the return lane",
            )
        if y == 3 and 11 <= x < 14:
            return self._decision(
                "right",
                "Auto: cut into Route 1's right-side return corridor",
            )
        if x == 14 and 3 <= y < 14:
            return self._decision(
                "down",
                "Auto: follow Route 1's right corridor south toward Pallet Town",
            )
        if y == 14 and 9 < x <= 14:
            return self._decision(
                "left",
                "Auto: shift west across Route 1's upper grass break on the return trip",
            )
        if x == 9 and 14 <= y < 20:
            return self._decision(
                "down",
                "Auto: descend Route 1's west corridor toward the mid-route bend",
            )
        if y == 20 and 9 <= x < 12:
            return self._decision(
                "right",
                "Auto: cross Route 1's mid-route opening back toward the south path",
            )
        if x == 12 and 20 <= y < 24:
            return self._decision(
                "down",
                "Auto: continue south through Route 1's central return lane",
            )
        if y == 24 and 8 < x <= 12:
            return self._decision(
                "left",
                "Auto: swing back west around Route 1's lower hedge",
            )
        if x == 8 and 24 <= y < 28:
            return self._decision(
                "down",
                "Auto: drop through Route 1's lower-left passage toward the south exit",
            )
        if y == 28 and 8 <= x < 11:
            return self._decision(
                "right",
                "Auto: realign with Route 1's final southbound strip into Pallet Town",
            )
        if x == 11 and 28 <= y <= 35:
            return self._decision(
                "down",
                "Auto: head through Route 1's south exit back into Pallet Town",
            )
        return None

    def _pallet_return_decision(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        """Guide the parcel return from Pallet Town's north gate back to Oak's Lab."""
        if x == 5 and 6 <= y < 8:
            return self._decision(
                "down",
                "Auto: step out from the player's house doorstep after a blackout so Oak's Parcel can still be returned",
            )
        if y == 8 and 5 <= x < 8:
            return self._decision(
                "right",
                "Auto: recover from the player's house side lane by rejoining Pallet Town's route back to Oak's Lab",
            )
        if x == 8 and 3 < y < 12:
            return self._decision(
                "down",
                "Auto: follow Pallet Town's west recovery lane south toward Oak's Lab after the blackout return home",
            )
        if y == 12 and 8 <= x < 12:
            return self._decision(
                "right",
                "Auto: cross Pallet Town's south lane from the recovery path to line up with Oak's Lab",
            )
        if x == 11 and 0 <= y < 2:
            return self._decision(
                "down",
                "Auto: step south out of Pallet Town's north grass opening",
            )
        if y == 2 and 1 <= x < 16:
            return self._decision(
                "right",
                "Auto: follow Pallet Town's north path east until the safe Oak's Lab return lane reconnects",
            )
        if x == 16 and 2 <= y < 12:
            return self._decision(
                "down",
                "Auto: descend Pallet Town's east path back toward Oak's Lab",
            )
        if y == 12 and 12 < x <= 16:
            return self._decision(
                "left",
                "Auto: cross Pallet Town's south lane to line up with Oak's Lab",
            )
        if x == 12 and y == 12:
            return self._decision(
                "up",
                "Auto: re-enter Oak's Lab to deliver Oak's Parcel",
            )
        return None

    def _oaks_lab_return_decision(
        self,
        x: int,
        y: int,
        item_count: int,
        screen_type: str,
    ) -> Optional[Dict[str, Any]]:
        """Walk back to Oak and start the parcel handoff inside Oak's Lab."""
        if x < 5 and 3 < y <= 11:
            return self._decision(
                "right",
                "Auto: center the player in Oak's Lab before approaching Oak",
            )
        if x == 5 and 3 < y <= 11:
            return self._decision(
                "up",
                "Auto: walk up Oak's Lab aisle toward Oak",
            )
        if x == 5 and y == 3 and screen_type not in {"dialogue", "battle"}:
            return self._decision(
                "a",
                "Auto: keep advancing Oak's parcel and Pokedex scene until the story flags confirm it is finished",
            )
        return None

    def _decision(self, action: str, reasoning: str) -> Dict[str, Any]:
        return {
            "action": action,
            "reasoning": reasoning,
            "goal_update": None,
            "recorded_in_context": False,
        }
