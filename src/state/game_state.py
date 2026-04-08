"""Game state processor combining memory data and optional harness-side vision."""

from typing import Dict, Any, Optional, List
from datetime import datetime

from ..emulator.game_boy import GameBoyEmulator
from ..emulator.memory_reader import MemoryReader
from .vision import VisionProcessor
from .map_memory import MapMemory
from ..utils.logger import get_logger


class GameState:
    """Comprehensive game state representation."""

    _LOW_PRIORITY_MOVE_IDS = {28, 39, 43, 45}
    _MOVE_ID_LABELS = {
        10: "Scratch",
        28: "Sand Attack",
        33: "Tackle",
        39: "Tail Whip",
        43: "Leer",
        45: "Growl",
        52: "Ember",
        55: "Water Gun",
        73: "Leech Seed",
    }

    def __init__(
        self,
        emulator: GameBoyEmulator,
        memory_reader: MemoryReader,
        vision_processor: Optional[VisionProcessor],
        map_memory: MapMemory,
        visual_enabled: bool = False,
        config: Optional[Any] = None,
    ):
        """Initialize game state processor.

        Args:
            emulator: GameBoy emulator instance
            memory_reader: Memory reader instance
            vision_processor: Vision processor instance
            map_memory: Map memory instance
            visual_enabled: Whether to run pixel-level vision analysis
            config: Optional shared configuration instance
        """
        self.emulator = emulator
        self.memory_reader = memory_reader
        self.vision = vision_processor
        self.map_memory = map_memory
        self.visual_enabled = visual_enabled
        self.config = config
        self.logger = get_logger("GameState")

        self.turn_count = 0
        self.last_update = None
        self._last_memory_state: Optional[Dict[str, Any]] = None
        self._position_history: List[Dict[str, int]] = []
        self._movement_stall_turns = 0
        self._battle_turns = 0
        self._battle_stall_turns = 0
        self._phase_hint: Optional[str] = None
        self._pre_starter_script_latched = False

    def _feature_enabled(self, path: str, default: bool = True) -> bool:
        """Return whether a feature flag is enabled in config."""
        config = getattr(self, "config", None)
        getter = getattr(config, "get", None)
        if callable(getter):
            value = getter(path, default)
            if value is None:
                return bool(default)
            return bool(value)
        return bool(default)

    def _build_navigation_decision_cues(
        self,
        state: Dict[str, Any],
        navigation: Dict[str, Any],
        vision_hints: Dict[str, Any],
    ) -> List[str]:
        """Distill one-step movement memory into prompt-friendly decision cues."""
        adjacent_tiles = navigation.get("adjacent_tiles", {}) or {}
        if not adjacent_tiles:
            return []

        vision_blocked = {
            str(direction or "").strip().lower()
            for direction in vision_hints.get("blocked_directions", []) or []
        }
        vision_unsafe = {
            str(direction or "").strip().lower()
            for direction in vision_hints.get("unsafe_directions", []) or []
        }
        warp_caution_directions = {
            str((item or {}).get("direction") or "").strip().lower()
            for item in navigation.get("warp_cautions", []) or []
            if str((item or {}).get("direction") or "").strip()
        }
        current_tile_trigger_action = str(
            (navigation.get("current_tile_warp", {}) or {}).get("trigger_action") or ""
        ).strip().lower()
        if current_tile_trigger_action:
            warp_caution_directions.add(current_tile_trigger_action)

        preferred: List[str] = []
        cautions: List[str] = []
        unverified: List[str] = []
        currently_blocked_known_routes = 0

        for direction in ("up", "down", "left", "right"):
            info = adjacent_tiles.get(direction) or {}
            status = str(info.get("status") or "unknown").strip().lower() or "unknown"
            blocked_attempts = int(info.get("blocked_attempts", 0) or 0)
            target_is_warp = bool(
                info.get("target_is_warp")
                or info.get("step_triggers_warp")
                or status == "warp_trigger"
                or direction in warp_caution_directions
            )
            if target_is_warp:
                warp_label = "warp"
                if status == "frontier" and info.get("is_preferred_frontier_step"):
                    warp_label = "warp+preferred_route"
                elif status in {"confirmed_blocked", "blocked_once"}:
                    warp_label = f"warp+{status}"
                cautions.append(f"{direction}={warp_label}")
                continue

            if blocked_attempts >= 2:
                if status == "known_exit":
                    cautions.append(f"{direction}=known_exit_but_currently_blocked")
                    currently_blocked_known_routes += 1
                elif status == "frontier":
                    cautions.append(f"{direction}=frontier_but_currently_blocked")
                elif status == "adjacent_explored":
                    cautions.append(f"{direction}=adjacent_explored_but_currently_blocked")
                else:
                    cautions.append(f"{direction}=confirmed_blocked")
                continue

            if blocked_attempts == 1 and status in {"known_exit", "frontier", "adjacent_explored"}:
                cautions.append(f"{direction}={status}_blocked_once")
                continue

            if status == "known_exit":
                preferred.append(f"{direction}=known_exit")
                continue

            if status == "frontier" and direction not in vision_blocked:
                if info.get("is_preferred_frontier_step"):
                    preferred.append(f"{direction}=frontier+preferred_route")
                elif direction in vision_unsafe:
                    cautions.append(f"{direction}=frontier_but_vision_unsafe")
                else:
                    preferred.append(f"{direction}=frontier")
                continue

            if status == "adjacent_explored" and direction not in vision_blocked:
                if direction in vision_unsafe:
                    cautions.append(f"{direction}=adjacent_explored_but_vision_unsafe")
                else:
                    preferred.append(f"{direction}=adjacent_explored")
                continue

            if status == "confirmed_blocked":
                cautions.append(f"{direction}=confirmed_blocked")
                continue

            if status == "blocked_once":
                cautions.append(f"{direction}=blocked_once")
                continue

            if direction in vision_blocked:
                cautions.append(f"{direction}=vision_blocked")
                continue

            if direction in vision_unsafe:
                cautions.append(f"{direction}=vision_unsafe")
                continue

            if status == "unknown":
                unverified.append(direction)

        cues: List[str] = []
        if preferred:
            cues.append(f"  Immediate movement preference: {', '.join(preferred)}")
        if unverified:
            cues.append(
                "  Unverified directions needing screenshot confirmation: "
                + ", ".join(unverified)
            )
        if cautions:
            cues.append(f"  Immediate movement cautions: {', '.join(cautions)}")

        memory = state.get("memory", {}) or {}
        ui_state = memory.get("ui", {}) or {}
        stall_turns = int((state.get("deltas", {}) or {}).get("movement_stall_turns", 0) or 0)
        if (
            not memory.get("in_battle")
            and not ui_state.get("text_box_active")
            and not ui_state.get("menu_active")
        ):
            if currently_blocked_known_routes >= 1 and stall_turns >= 1:
                cues.append(
                    "  Interaction cue: a route that previously worked is currently blocked "
                    "from this tile. Suspect an NPC or story lock; if the screenshot shows "
                    "Oak, the rival, or another blocker nearby, try A instead of repeating "
                    "the old movement."
                )
            elif not preferred and not unverified:
                cues.append(
                    "  Interaction cue: local movement options look exhausted in memory; "
                    "if the screenshot shows a nearby blocker, NPC, or trigger, press A "
                    "instead of repeating blocked movement."
                )
            elif stall_turns >= 2 and len(cautions) >= 2:
                cues.append(
                    "  Interaction cue: repeated local movement failures suggest a blocker "
                    "or script lock; if the route is visibly blocked by Oak, the rival, "
                    "or another obstacle, try A."
                )

        return cues

    def _story_guidance_payload(
        self,
        summary: str,
        *,
        phase: str = "post_battle_intro_route",
        priority: str = "high",
    ) -> Dict[str, Any]:
        """Build a consistent story-guidance payload."""
        return {
            "phase": phase,
            "priority": priority,
            "summary": summary,
        }

    def _build_outbound_story_guidance(
        self,
        map_id: int,
        x: int,
        y: int,
    ) -> Optional[Dict[str, Any]]:
        """Guide the first walk from Oak's Lab to Viridian Mart using text cues only."""
        if map_id == 40 and 3 <= y <= 11:
            if y == 11 and x < 4:
                summary = (
                    "Early-story verified map fact: Oak's Lab exit warp is on row y=11 at x=4 or x=5. "
                    "You drifted too far left, so move RIGHT back to x=4 or x=5. Once aligned on those "
                    "door columns, press DOWN to leave instead of exploring the left wall."
                )
            elif y == 11 and x > 5:
                summary = (
                    "Early-story verified map fact: Oak's Lab exit warp is on row y=11 at x=4 or x=5. "
                    "You are already on the bottom row but still to the right of the exit, so move LEFT "
                    "until you reach x=4 or x=5, then press DOWN to leave instead of exploring deeper into the lab."
                )
            elif y == 11:
                summary = (
                    "Early-story verified map fact: you are already standing on Oak's Lab exit columns "
                    "x=4 or x=5 on row y=11. Press DOWN now to leave the lab."
                )
            elif x < 4:
                summary = (
                    "Early-story verified map fact: Oak's Lab exit warp is on row y=11 at x=4 or x=5. "
                    "First move RIGHT toward the exit columns, then work DOWN to the bottom row."
                )
            elif x > 5:
                summary = (
                    "Early-story verified map fact: Oak's Lab exit warp is on row y=11 at x=4 or x=5. "
                    "First line up by moving LEFT toward the exit columns, then work DOWN to the bottom row."
                )
            else:
                summary = (
                    "Early-story verified map fact: Oak's Lab exit warp is on row y=11 at x=4 or x=5. "
                    "You are already near the correct columns, so work DOWN toward the bottom exit instead "
                    "of re-exploring the upper aisles."
                )
            return self._story_guidance_payload(summary)

        if map_id == 0:
            if x > 9 and y >= 12:
                return self._story_guidance_payload(
                    "Early-story verified route from the latest post-rival checkpoint: outside Oak's Lab, "
                    "do not drift around the east side. Along the lab frontage near y=12, move LEFT until "
                    "you reach x=9; on these doorway tiles, UP usually does not advance north yet and "
                    "stepping back onto the lab doorway risks re-entry."
                )
            if x == 9 and y > 2:
                return self._story_guidance_payload(
                    "Early-story verified route: once you reach Pallet Town's west-side lane at x=9, "
                    "keep moving UP repeatedly until about y=2 instead of wandering back toward the lab."
                )
            if x < 9 and y > 2:
                return self._story_guidance_payload(
                    "Early-story recovery route: you are left of Pallet Town's intended west-side lane. "
                    "Shift RIGHT back toward x=9, then continue UP toward the north exit.",
                    priority="medium",
                )
            if x < 10 and y <= 2:
                return self._story_guidance_payload(
                    "Early-story verified route near Pallet Town's north edge: shift RIGHT toward x=10, "
                    "then press UP through the Route 1 opening."
                )
            if 10 <= x <= 11 and y <= 2:
                return self._story_guidance_payload(
                    "Early-story objective: exit Pallet Town north into Route 1. You are aligned with "
                    "the north opening now, so prioritize UP over sideways town exploration."
                )
            if x > 11 and y <= 2:
                return self._story_guidance_payload(
                    "Early-story objective: line up with Pallet Town's north opening. Shift LEFT toward "
                    "x=10 or x=11, then keep working UP into Route 1.",
                    priority="medium",
                )
            return None

        if map_id == 12:
            if y >= 34 and x > 10:
                return self._story_guidance_payload(
                    "Early-story verified Route 1 entry: from the south opening, first shift LEFT into "
                    "the left corridor around x=10, then continue UP instead of fighting the hedge from the "
                    "far-right edge."
                )
            if x == 10 and 28 < y <= 35:
                return self._story_guidance_payload(
                    "Verified Route 1 segment: stay in the left corridor at x=10 and keep moving UP until "
                    "you reach the bend near y=28."
                )
            if y == 28 and 8 < x <= 11:
                return self._story_guidance_payload(
                    "Verified Route 1 bend: on row y=28, shift LEFT until x=8 before trying to climb again."
                )
            if x == 8 and 26 < y <= 28:
                return self._story_guidance_payload(
                    "Verified Route 1 opening: once aligned at x=8, press UP through the first north gap."
                )
            if y == 26 and 8 <= x < 10:
                return self._story_guidance_payload(
                    "Verified Route 1 cross-lane: on row y=26, move RIGHT to x=10 to line up with the "
                    "middle corridor."
                )
            if x == 10 and 24 < y <= 26:
                return self._story_guidance_payload(
                    "Verified Route 1 middle corridor: keep moving UP on x=10 until the dogleg at y=24."
                )
            if (x, y) == (10, 24):
                return self._story_guidance_payload(
                    "Verified Route 1 dogleg: step RIGHT once from (10,24) to enter the narrow bend."
                )
            if (x, y) == (11, 24):
                return self._story_guidance_payload(
                    "Verified Route 1 dogleg: from (11,24), go DOWN one tile to (11,25) so the right-side "
                    "lane opens."
                )
            if (x, y) == (11, 25):
                return self._story_guidance_payload(
                    "Verified Route 1 dogleg: from (11,25), go RIGHT once to enter the upper-right lane."
                )
            if x == 12 and 20 < y <= 25:
                return self._story_guidance_payload(
                    "Verified Route 1 upper-right lane: keep moving UP on x=12 until the cross-lane at y=20."
                )
            if y == 20 and 9 < x <= 12:
                return self._story_guidance_payload(
                    "Verified Route 1 upper cross-lane: on row y=20, shift LEFT to x=9 before climbing again."
                )
            if x == 9 and 14 < y <= 20:
                return self._story_guidance_payload(
                    "Verified Route 1 upper-left lane: keep moving UP on x=9 toward the Viridian approach."
                )
            if y == 14 and 9 <= x < 15:
                return self._story_guidance_payload(
                    "Verified Route 1 top corridor: move RIGHT along row y=14 until x=15."
                )
            if x == 15 and 2 < y <= 14:
                return self._story_guidance_payload(
                    "Verified Route 1 final straight: keep moving UP on x=15 toward Viridian City's south gate."
                )
            if y == 2 and 11 < x <= 15:
                return self._story_guidance_payload(
                    "Verified Route 1 north exit: on row y=2, shift LEFT until x=11 to line up with the gate."
                )
            if x == 11 and y <= 2:
                return self._story_guidance_payload(
                    "Verified Route 1 objective: you are aligned with Viridian City's south gate now, so "
                    "prioritize UP through the north exit."
                )
            return None

        if map_id == 1:
            if x == 21 and 30 < y <= 35:
                return self._story_guidance_payload(
                    "Verified Viridian south gate: keep moving UP on x=21 until the sign blocks the center lane."
                )
            if (x, y) == (21, 30):
                return self._story_guidance_payload(
                    "Verified Viridian choke point: from (21,30), step LEFT once to clear the south sign."
                )
            if x == 20 and 28 < y <= 30:
                return self._story_guidance_payload(
                    "Verified Viridian south approach: keep moving UP on x=20 until you reach y=28."
                )
            if (x, y) == (20, 28):
                return self._story_guidance_payload(
                    "Verified Viridian hedge opening: from (20,28), step LEFT once to x=19."
                )
            if (x, y) == (19, 28):
                return self._story_guidance_payload(
                    "Verified Viridian hedge opening: from (19,28), go UP through the gap onto the main road."
                )
            if x == 19 and 16 < y <= 27:
                return self._story_guidance_payload(
                    "Verified Viridian main road: keep moving UP on x=19 until the mart turnoff at y=16."
                )
            if x == 19 and 14 <= y < 16:
                return self._story_guidance_payload(
                    "Verified Viridian mart turnoff: if you overshoot above y=16 on x=19, step DOWN back to y=16 "
                    "before moving east."
                )
            if y == 16 and 19 <= x < 27:
                return self._story_guidance_payload(
                    "Verified Viridian mart road: on row y=16, move RIGHT toward x=27 to reach the Pokemart lane."
                )
            if x == 27 and 16 <= y < 20:
                return self._story_guidance_payload(
                    "Verified Viridian mart lane: move DOWN on x=27 until y=20."
                )
            if y == 20 and 27 <= x < 29:
                return self._story_guidance_payload(
                    "Verified Viridian mart approach: move RIGHT along row y=20 until the doorway at x=29."
                )
            if x == 29 and y == 20:
                return self._story_guidance_payload(
                    "Verified Viridian objective: step UP from (29,20) to enter Viridian Mart."
                )
            return None

        if map_id == 42:
            return self._story_guidance_payload(
                "Inside Viridian Mart before Oak's Parcel: stay in front of the clerk long enough for the "
                "script to start, then press A through the dialogue until Oak's Parcel is received."
            )

        return None

    def _build_parcel_return_story_guidance(
        self,
        map_id: int,
        x: int,
        y: int,
        ui_state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Guide the first parcel return trip back to Oak using text cues only."""
        phase = "viridian_parcel_return"

        if map_id == 42:
            if bool(ui_state.get("text_box_active")):
                return self._story_guidance_payload(
                    "Parcel return scene: dialogue is active in Viridian Mart, so keep pressing A until the "
                    "handoff finishes and control returns.",
                    phase=phase,
                )
            if x < 3:
                return self._story_guidance_payload(
                    "Parcel return route: inside Viridian Mart, move RIGHT until you line up with the exit warp "
                    "columns around x=3.",
                    phase=phase,
                )
            if y < 7:
                return self._story_guidance_payload(
                    "Parcel return route: once lined up with the exit columns, move DOWN toward the mart door "
                    "warp on the bottom row.",
                    phase=phase,
                )
            return self._story_guidance_payload(
                "Parcel return objective: leave Viridian Mart, then head south through Route 1 to Oak's Lab.",
                phase=phase,
            )

        if map_id == 1:
            if (x, y) == (29, 19):
                return self._story_guidance_payload(
                    "Parcel return route: from Viridian Mart's doorway tile, step DOWN once before heading west.",
                    phase=phase,
                )
            if y == 20 and 19 < x <= 29:
                return self._story_guidance_payload(
                    "Parcel return route: on Viridian City's lower east lane, move LEFT back toward the main road "
                    "at x=19.",
                    phase=phase,
                )
            if x == 19 and 20 <= y < 28:
                return self._story_guidance_payload(
                    "Parcel return route: keep moving DOWN on x=19 toward Viridian City's south exit.",
                    phase=phase,
                )
            if x == 19 and y == 28:
                return self._story_guidance_payload(
                    "Parcel return route: from (19,28), step RIGHT to re-enter the south gate lane.",
                    phase=phase,
                )
            if x == 20 and 28 <= y < 30:
                return self._story_guidance_payload(
                    "Parcel return route: move DOWN on x=20 until y=30.",
                    phase=phase,
                )
            if x == 20 and y == 30:
                return self._story_guidance_payload(
                    "Parcel return route: from (20,30), step RIGHT once back into the center exit lane.",
                    phase=phase,
                )
            if x == 21 and 30 <= y <= 35:
                return self._story_guidance_payload(
                    "Parcel return objective: keep moving DOWN on x=21 to leave Viridian City through the south gate.",
                    phase=phase,
                )
            return None

        if map_id == 12:
            if x == 11 and 0 <= y < 3:
                return self._story_guidance_payload(
                    "Parcel return Route 1 segment: keep moving DOWN on x=11 until the path opens east at y=3.",
                    phase=phase,
                )
            if y == 3 and 11 <= x < 14:
                return self._story_guidance_payload(
                    "Parcel return Route 1 segment: on row y=3, move RIGHT until x=14 to enter the southbound lane.",
                    phase=phase,
                )
            if x == 14 and 3 <= y < 14:
                return self._story_guidance_payload(
                    "Parcel return Route 1 segment: keep moving DOWN on x=14 through the long right corridor.",
                    phase=phase,
                )
            if y == 14 and 9 < x <= 14:
                return self._story_guidance_payload(
                    "Parcel return Route 1 segment: on row y=14, shift LEFT until x=9.",
                    phase=phase,
                )
            if x == 9 and 14 <= y < 20:
                return self._story_guidance_payload(
                    "Parcel return Route 1 segment: keep moving DOWN on x=9 toward the mid-route opening.",
                    phase=phase,
                )
            if y == 20 and 9 <= x < 12:
                return self._story_guidance_payload(
                    "Parcel return Route 1 segment: on row y=20, move RIGHT toward x=12.",
                    phase=phase,
                )
            if x == 12 and 20 <= y < 24:
                return self._story_guidance_payload(
                    "Parcel return Route 1 segment: keep moving DOWN on x=12 to the lower bend.",
                    phase=phase,
                )
            if y == 24 and 8 < x <= 12:
                return self._story_guidance_payload(
                    "Parcel return Route 1 segment: on row y=24, shift LEFT until x=8.",
                    phase=phase,
                )
            if x == 8 and 24 <= y < 28:
                return self._story_guidance_payload(
                    "Parcel return Route 1 segment: keep moving DOWN on x=8 through the lower-left passage.",
                    phase=phase,
                )
            if y == 28 and 8 <= x < 11:
                return self._story_guidance_payload(
                    "Parcel return Route 1 segment: on row y=28, move RIGHT until x=11 to line up with the south exit.",
                    phase=phase,
                )
            if x == 11 and 28 <= y <= 35:
                return self._story_guidance_payload(
                    "Parcel return objective: keep moving DOWN on x=11 to re-enter Pallet Town.",
                    phase=phase,
                )
            return None

        if map_id == 0:
            if x == 11 and 0 <= y < 2:
                return self._story_guidance_payload(
                    "Parcel return route in Pallet Town: step DOWN out of the north gate grass before turning east.",
                    phase=phase,
                )
            if y == 2 and 1 <= x < 16:
                return self._story_guidance_payload(
                    "Parcel return route in Pallet Town: move RIGHT along the north path until x=16.",
                    phase=phase,
                )
            if x == 16 and 2 <= y < 12:
                return self._story_guidance_payload(
                    "Parcel return route in Pallet Town: keep moving DOWN on x=16 toward Oak's Lab.",
                    phase=phase,
                )
            if y == 12 and 12 < x <= 16:
                return self._story_guidance_payload(
                    "Parcel return route in Pallet Town: on row y=12, move LEFT until x=12 to line up with Oak's Lab.",
                    phase=phase,
                )
            if x == 12 and y == 12:
                return self._story_guidance_payload(
                    "Parcel return objective: press UP from (12,12) to re-enter Oak's Lab.",
                    phase=phase,
                )
            return None

        if map_id == 40:
            if x < 5 and 3 < y <= 11:
                return self._story_guidance_payload(
                    "Parcel return route in Oak's Lab: move RIGHT until x=5 to line up with Oak's aisle.",
                    phase=phase,
                )
            if x == 5 and 3 < y <= 11:
                return self._story_guidance_payload(
                    "Parcel return route in Oak's Lab: keep moving UP on x=5 until you stand directly below Oak.",
                    phase=phase,
                )
            if x == 5 and y == 3:
                if bool(ui_state.get("text_box_active")):
                    return self._story_guidance_payload(
                        "Parcel return scene: Oak dialogue is active, so keep pressing A until the parcel and "
                        "Pokedex sequence finishes.",
                        phase=phase,
                    )
                return self._story_guidance_payload(
                    "Parcel return objective: press A while facing Oak at (5,3) to start the delivery scene.",
                    phase=phase,
                )
            return None

        return None

    def _build_story_guidance(
        self,
        memory_state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Surface narrow early-story objective cues without taking control away from the AI."""
        if not self._feature_enabled("state.story_guidance_enabled", True):
            return None
        if memory_state.get("in_battle"):
            return None

        events = memory_state.get("events", {}) or {}
        got_oaks_parcel = bool(events.get("got_oaks_parcel"))
        oak_got_parcel = bool(events.get("oak_got_parcel"))
        got_pokedex = bool(events.get("got_pokedex"))
        if got_pokedex or oak_got_parcel:
            return None

        if int(memory_state.get("badge_count", 0) or 0) != 0:
            return None
        item_count = int(memory_state.get("item_count", 0) or 0)
        if int(memory_state.get("money", 0) or 0) < 3175:
            return None

        party = list(memory_state.get("party", []) or [])
        if len(party) != 1:
            return None

        starter = party[0] or {}
        starter_level = int(starter.get("level", 0) or 0)
        if starter_level < 6 or starter_level > 10:
            return None

        position = memory_state.get("position", {}) or {}
        ui_state = memory_state.get("ui", {}) or {}
        map_id_raw = position.get("map_id", -1)
        x_raw = position.get("x", -1)
        y_raw = position.get("y", -1)
        map_id = int(-1 if map_id_raw is None else map_id_raw)
        x = int(-1 if x_raw is None else x_raw)
        y = int(-1 if y_raw is None else y_raw)

        if got_oaks_parcel or item_count > 0:
            return self._build_parcel_return_story_guidance(map_id, x, y, ui_state)

        return self._build_outbound_story_guidance(map_id, x, y)

    def _describe_move(self, move: Dict[str, Any], slot_index: int) -> Dict[str, Any]:
        """Normalize move info into prompt-friendly battle labels."""
        move_id = int((move or {}).get("move_id", 0) or 0)
        pp = int((move or {}).get("pp", 0) or 0)
        if move_id <= 0:
            name = "Unknown"
        else:
            name = self._MOVE_ID_LABELS.get(move_id, f"Move#{move_id}")
        role = "status" if move_id in self._LOW_PRIORITY_MOVE_IDS else "damaging"
        return {
            "slot": slot_index,
            "move_id": move_id,
            "name": name,
            "pp": pp,
            "role": role,
            "usable": move_id > 0 and pp > 0,
        }

    def _build_battle_guidance(
        self,
        memory_state: Dict[str, Any],
        battle_summary: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Turn battle RAM into actionable next-step cues for the model."""
        if not self._feature_enabled("state.battle_guidance_enabled", True):
            return None
        phase = str(battle_summary.get("phase") or "not_in_battle").strip().lower()
        in_battle = bool(memory_state.get("in_battle"))
        ui_state = memory_state.get("ui", {}) or {}
        if not in_battle and phase not in {"post_battle_dialogue", "battle_just_ended"}:
            return None

        party = list(memory_state.get("party", []) or [])
        lead = party[0] if party else {}
        usable_moves = [
            self._describe_move(move, slot_index)
            for slot_index, move in enumerate((lead or {}).get("moves", []) or [], start=1)
        ]
        usable_moves = [move for move in usable_moves if move.get("move_id", 0) > 0]
        preferred_move = next(
            (move for move in usable_moves if move.get("usable") and move.get("role") != "status"),
            None,
        )
        fallback_move = next((move for move in usable_moves if move.get("usable")), None)
        status_moves = [
            move for move in usable_moves if move.get("usable") and move.get("role") == "status"
        ]

        enemy_hp_raw = (memory_state.get("battle", {}) or {}).get("enemy_current_hp")
        try:
            enemy_hp = None if enemy_hp_raw is None else int(enemy_hp_raw)
        except (TypeError, ValueError):
            enemy_hp = None

        summary = ""
        if phase == "post_battle_dialogue":
            summary = (
                "Battle result dialogue is still active. Keep advancing the text with A until "
                "the result box fully closes before trying to move."
            )
        elif phase == "battle_just_ended":
            summary = (
                "The battle just ended. Confirm the screenshot is back to the field before "
                "switching from text advancement to movement."
            )
        elif ui_state.get("text_box_active"):
            summary = (
                "Battle text is still the active UI. Press A to advance encounter, send-out, "
                "attack, or result text until a real menu becomes visible."
            )
        elif ui_state.get("menu_active") and enemy_hp is not None and enemy_hp <= 0:
            summary = (
                "The enemy has already fainted, so any visible menu is probably stale. Press B "
                "to close it and let the victory text continue."
            )
        elif ui_state.get("menu_active"):
            summary = (
                "A battle menu is active. If this is the four-command menu, choose FIGHT. If "
                "the move list is already open, pick the recommended move directly."
            )
        else:
            summary = (
                "A battle is active but RAM does not show a clean menu yet. Use the screenshot "
                "to confirm whether battle text is still animating; if no actionable menu is "
                "visible, A is the safest progress input."
            )

        menu_cue = None
        if in_battle and phase in {"entered_battle", "battle_in_progress"} and enemy_hp != 0:
            menu_cue = (
                "When the standard four-command battle menu appears, prefer FIGHT over BAG, "
                "PKMN, or RUN for this ordinary early-game encounter unless the screenshot shows "
                "a different urgent need."
            )

        move_cue = None
        chosen_move = preferred_move or fallback_move
        if chosen_move:
            move_cue = (
                f"When the move list is open, prefer slot {chosen_move['slot']} "
                f"({chosen_move['name']}, PP {chosen_move['pp']})"
            )
            if preferred_move and status_moves:
                avoided = ", ".join(
                    f"slot {move['slot']} ({move['name']})" for move in status_moves
                )
                move_cue += f"; avoid status-only options like {avoided} while a damaging move still has PP."
            else:
                move_cue += "."

        hp_cue = None
        lead_info = battle_summary.get("lead_pokemon") or {}
        if float(lead_info.get("hp_percent", 0.0) or 0.0) <= 25.0:
            hp_cue = (
                "Your lead Pokemon is low HP, so do not random-walk through menus. Finish text "
                "cleanly and choose the intended battle option directly."
            )

        return {
            "phase": phase,
            "priority": "high" if in_battle else "medium",
            "summary": summary,
            "menu_cue": menu_cue,
            "move_cue": move_cue,
            "hp_cue": hp_cue,
        }

    @staticmethod
    def is_pre_world_state(memory_state: Dict[str, Any]) -> bool:
        """Return True before the player is in a reliable in-world map state."""
        position = memory_state.get("position", {})
        ui = memory_state.get("ui", {})
        return (
            int(position.get("map_id", -1)) == 0
            and int(position.get("x", -1)) == 0
            and int(position.get("y", -1)) == 0
            and not memory_state.get("party")
            and not memory_state.get("money")
            and not memory_state.get("item_count")
            and not memory_state.get("in_battle")
            and not ui.get("menu_active")
            and not ui.get("text_box_active")
        )

    @staticmethod
    def is_pre_starter_script_state(
        memory_state: Dict[str, Any],
        phase_hint: Optional[str],
    ) -> bool:
        """Return True when early scripted intro screens are active before free movement."""
        if memory_state.get("party") or memory_state.get("in_battle"):
            return False

        hint = (phase_hint or "").strip().lower()
        return hint in {
            "startup",
            "title",
            "startup_menu",
            "options_menu",
            "dialogue",
            "cutscene",
            "text_entry",
            "naming_screen",
            "menu",
        }

    def set_phase_hint(self, phase_hint: Optional[str]) -> None:
        """Store an external UI-phase hint for the next update call."""
        self._phase_hint = phase_hint

    def update(self, screen_image=None) -> Dict[str, Any]:
        """Update and return current game state."""
        self.turn_count += 1
        self.last_update = datetime.now()

        # Get memory data
        memory_state = self.memory_reader.get_game_state_summary()
        deltas = self._compute_memory_deltas(memory_state)
        pre_world = self.is_pre_world_state(memory_state)
        observed_pre_starter_script = self.is_pre_starter_script_state(memory_state, self._phase_hint)
        if observed_pre_starter_script:
            self._pre_starter_script_latched = True
        elif self._pre_starter_script_latched:
            position = memory_state.get("position", {})
            hint = (self._phase_hint or "").strip().lower()
            free_movement_signal = (
                bool(deltas.get("position_changed"))
                and int(position.get("map_id", 0)) != 0
                and hint not in {
                    "startup",
                    "title",
                    "startup_menu",
                    "options_menu",
                    "dialogue",
                    "cutscene",
                    "text_entry",
                    "naming_screen",
                    "menu",
                }
            )
            if free_movement_signal or memory_state.get("party") or memory_state.get("in_battle"):
                self._pre_starter_script_latched = False
        pre_starter_script = self._pre_starter_script_latched or observed_pre_starter_script

        # Get visual analysis or placeholder
        if screen_image is None:
            screen_image = self.emulator.get_screen_image()
        visual_analysis = self._get_visual_analysis(screen_image)

        previous_position = None
        if self._last_memory_state:
            previous_position = self._last_memory_state.get("position")
        position = memory_state["position"]
        if pre_world or pre_starter_script:
            exploration = {
                "map_id": None,
                "explored_count": 0,
                "total_tiles": 0,
                "exploration_percent": 0.0,
                "nearby_unexplored": [],
                "frontier_count": 0,
            }
            navigation = {
                "available": False,
                "current_visit_count": 0,
                "known_exits": {},
                "blocked_directions": [],
                "frontier_count": 0,
                "nearest_frontier": None,
                "adjacent_tiles": {},
                "local_map": [],
            }
            map_memory_state = {
                "current_map": None,
                "explored_tiles": 0,
                "total_tiles": 0,
                "exploration_percent": 0.0,
            }
        else:
            self.map_memory.update_position(
                position["map_id"],
                position["x"],
                position["y"],
                previous_position=previous_position,
            )
            self._update_position_history(position)
            exploration = self.map_memory.get_exploration_status(position["map_id"])
            navigation = exploration.get("navigation") or self.map_memory.get_navigation_advice(
                position["map_id"],
                position["x"],
                position["y"],
            )
            if isinstance(navigation, dict) and "map_snapshot" not in navigation:
                navigation["map_snapshot"] = self.map_memory.build_map_snapshot(
                    position["map_id"],
                    current_position=(position["x"], position["y"]),
                )
            map_memory_state = {
                "current_map": position["map_id"],
                "explored_tiles": exploration["explored_count"],
                "total_tiles": exploration["total_tiles"],
                "exploration_percent": exploration["exploration_percent"],
            }
        story_guidance = None if (pre_world or pre_starter_script) else self._build_story_guidance(memory_state)
        battle_summary = self._analyze_battle_state(memory_state)
        battle_guidance = self._build_battle_guidance(memory_state, battle_summary)
        movement_pattern = self._analyze_recent_movement(memory_state)

        # Combine into comprehensive state
        state = {
            "turn": self.turn_count,
            "timestamp": self.last_update.isoformat(),
            "memory": memory_state,
            "pre_world": pre_world,
            "pre_starter_script": pre_starter_script,
            "phase_hint": self._phase_hint,
            "visual": visual_analysis,
            "exploration": exploration,
            "map_memory": map_memory_state,
            "navigation": navigation,
            "story_guidance": story_guidance,
            "deltas": deltas,
            "movement_pattern": movement_pattern,
            "battle_summary": battle_summary,
            "battle_guidance": battle_guidance,
        }

        self._last_memory_state = memory_state
        self.logger.state("full_state", state)

        return state

    def reset_tracking(self, turn_count: int = 0) -> None:
        """Reset delta/history tracking after loading a checkpoint."""
        self.turn_count = max(0, int(turn_count))
        self.last_update = None
        self._last_memory_state = None
        self._position_history = []
        self._movement_stall_turns = 0
        self._battle_turns = 0
        self._battle_stall_turns = 0
        self._phase_hint = None
        self._pre_starter_script_latched = False

    def get_text_representation(self, state: Optional[Dict[str, Any]] = None) -> str:
        """Convert game state to text representation for AI."""
        if state is None:
            state = self.update()

        memory = state["memory"]
        position = memory["position"]
        badges = memory["badges"]
        party = memory["party"]
        visual = state["visual"]
        deltas = state.get("deltas", {})
        battle = memory.get("battle", {})
        battle_summary = state.get("battle_summary", {}) or {}
        ui_state = memory.get("ui", {})
        navigation = state.get("navigation", {})
        vision_hints = visual.get("navigation_hints", {})
        local_vision_enabled = bool(visual.get("local_analysis_enabled", False))
        pre_world = bool(state.get("pre_world"))
        pre_starter_script = bool(state.get("pre_starter_script"))
        phase_hint = state.get("phase_hint") or "unknown"
        text = f"""=== GAME STATE (Turn {state['turn']}) ===

POSITION:
- Map ID: {position['map_id']}
- Coordinates: ({position['x']}, {position['y']})
- Facing: {memory.get('direction', 'unknown')}
- Harness UI Classification: {visual.get('screen_type', 'unknown')}
- External UI Hint: {phase_hint}
- Harness Local Vision: {'enabled' if local_vision_enabled else 'disabled'}

BADGES: {memory['badge_count']}/8
"""
        for badge_name, obtained in badges.items():
            status = "[X]" if obtained else "[ ]"
            text += f"  {status} {badge_name}\n"

        text += f"\nMONEY: ${memory['money']}\n"
        text += f"ITEMS IN BAG: {memory.get('item_count', 0)}\n"

        text += f"\nPARTY: {len(party)} Pokemon\n"
        for i, pokemon in enumerate(party, 1):
            hp_percent = (
                (pokemon["current_hp"] / pokemon["max_hp"] * 100)
                if pokemon["max_hp"] > 0
                else 0
            )
            text += (
                f"  {i}. {pokemon['species']} Lv.{pokemon['level']} - "
                f"HP: {pokemon['current_hp']}/{pokemon['max_hp']} ({hp_percent:.0f}%)\n"
            )
            move_chunks = []
            for slot_index, move in enumerate(pokemon["moves"], start=1):
                move_info = self._describe_move(move, slot_index)
                move_chunks.append(
                    f"{slot_index}:{move_info['name']} [{move_info['role']}, PP:{move_info['pp']}]"
                )
            text += "     Moves: " + ("; ".join(move_chunks) if move_chunks else "none") + "\n"

        if memory["in_battle"]:
            text += "\nBATTLE: CURRENTLY IN BATTLE\n"
            text += f"  Type: {battle.get('battle_type', 'unknown')}\n"
            text += (
                f"  Enemy: {battle.get('enemy_species', 'Unknown')} "
                f"Lv.{battle.get('enemy_level', '?')} "
                f"HP:{battle.get('enemy_current_hp', '?')}\n"
            )

        battle_phase = battle_summary.get("phase")
        if battle_phase and battle_phase != "not_in_battle":
            text += "\nBATTLE SUMMARY:\n"
            text += f"  Phase: {battle_phase}\n"
            text += f"  Encounter type: {battle_summary.get('encounter_type', 'unknown')}\n"
            text += f"  Consecutive battle turns: {battle_summary.get('battle_turns', 0)}\n"
            text += (
                f"  Enemy HP changed this turn: "
                f"{battle_summary.get('enemy_hp_changed', False)}\n"
            )
            text += f"  Battle stall turns: {battle_summary.get('battle_stall_turns', 0)}\n"
            lead = battle_summary.get("lead_pokemon") or {}
            if lead:
                text += (
                    f"  Lead Pokemon: {lead.get('species', 'Unknown')} "
                    f"Lv.{lead.get('level', '?')} "
                    f"HP:{lead.get('current_hp', '?')}/{lead.get('max_hp', '?')} "
                    f"({lead.get('hp_percent', 0):.0f}%)\n"
                )
            focus_hint = battle_summary.get("focus_hint")
            if focus_hint:
                text += f"  Focus hint: {focus_hint}\n"

        battle_guidance = state.get("battle_guidance")
        if battle_guidance is None and self._feature_enabled("state.battle_guidance_enabled", True):
            battle_guidance = self._build_battle_guidance(memory, battle_summary)
        if (battle_guidance or {}).get("summary"):
            text += "\nBATTLE GUIDANCE:\n"
            text += f"  Phase: {battle_guidance.get('phase', 'unknown')}\n"
            text += f"  Priority: {battle_guidance.get('priority', 'unknown')}\n"
            text += f"  Cue: {battle_guidance.get('summary')}\n"
            if battle_guidance.get("menu_cue"):
                text += f"  Menu cue: {battle_guidance.get('menu_cue')}\n"
            if battle_guidance.get("move_cue"):
                text += f"  Move cue: {battle_guidance.get('move_cue')}\n"
            if battle_guidance.get("hp_cue"):
                text += f"  HP cue: {battle_guidance.get('hp_cue')}\n"

        text += "\nUI FLAGS:\n"
        text += f"  Text box active (RAM): {ui_state.get('text_box_active', False)}\n"
        text += f"  Menu active (RAM): {ui_state.get('menu_active', False)}\n"
        if (
            ui_state.get("text_box_active")
            and visual.get("screen_type") in {"indoor", "overworld"}
        ):
            text += "  Text-box caution: RAM still says text is active, but the screenshot looks like a room/map rather than a clear dialogue panel. Treat this as a possibly stale UI flag.\n"

        text += "\nPERCEPTION SUMMARY:\n"
        text += f"  Harness note: {visual.get('description', 'n/a')}\n"
        if pre_world:
            text += "  World-state note: the game has not reached a reliable in-world map yet. Ignore map coordinates and old exploration memory; rely on the screenshot to get through boot/title/intro screens.\n"
        elif pre_starter_script:
            text += "  World-state note: early scripted intro is still active before the first Pokemon. Even if map coordinates are populated, do not treat them as free-movement navigation state yet; rely on the screenshot until control is clearly returned.\n"
        if visual.get("detailed_elements"):
            text += f"  Elements: {', '.join(str(item) for item in visual.get('detailed_elements', [])[:8])}\n"

        story_guidance = state.get("story_guidance") or {}
        if story_guidance.get("summary"):
            text += "\nSTORY GUIDANCE:\n"
            text += f"  Phase: {story_guidance.get('phase', 'unknown')}\n"
            text += f"  Priority: {story_guidance.get('priority', 'unknown')}\n"
            text += f"  Cue: {story_guidance.get('summary')}\n"

        if vision_hints and vision_hints.get("available"):
            blocked_dirs = ", ".join(vision_hints.get("blocked_directions", [])) or "none"
            unsafe_dirs = ", ".join(vision_hints.get("unsafe_directions", [])) or "none"
            walkable_dirs = ", ".join(vision_hints.get("walkable_directions", [])) or "none"
            text += f"  Vision-blocked directions: {blocked_dirs}\n"
            text += f"  Vision-unsafe directions: {unsafe_dirs}\n"
            text += f"  Vision-preferred walkable directions: {walkable_dirs}\n"

        # Memory-only deltas to help the LLM detect being stuck
        text += "\nSTATE DELTAS (memory-based):\n"
        text += f"  Position changed: {deltas.get('position_changed', False)}\n"
        text += f"  Money delta: {deltas.get('money_delta', 0)}\n"
        text += f"  Battle toggled: {deltas.get('battle_toggled', False)}\n"
        text += f"  Movement stall turns: {deltas.get('movement_stall_turns', 0)}\n"
        text += f"  Stuck hint: {deltas.get('stuck_hint', 'unknown')}\n"
        movement_pattern = state.get("movement_pattern", {}) or {}
        if movement_pattern.get("window_size", 0):
            text += "\nMOVEMENT PATTERN:\n"
            text += f"  Recent same-map positions tracked: {movement_pattern.get('window_size', 0)}\n"
            text += f"  Unique recent tiles: {movement_pattern.get('unique_tiles', 0)}\n"
            text += (
                f"  Recent movement box: "
                f"{movement_pattern.get('bounding_box_width', 0)}x"
                f"{movement_pattern.get('bounding_box_height', 0)}\n"
            )
            text += (
                f"  Current tile repeats in window: "
                f"{movement_pattern.get('current_tile_repeat_count', 0)}\n"
            )
            warning = movement_pattern.get("warning")
            text += f"  Loop warning: {warning or 'none'}\n"

        text += f"\nEXPLORATION:\n"
        if pre_world or pre_starter_script:
            text += "  Not available yet. Wait until the game reaches a real map or indoor room.\n"
        else:
            text += (
                f"  Current Map Explored: "
                f"{state['map_memory']['exploration_percent']:.1f}%\n"
            )
            text += (
                f"  Tiles Explored: {state['map_memory']['explored_tiles']}/"
                f"{state['map_memory']['total_tiles']}\n"
            )

            unexplored = state["exploration"].get("nearby_unexplored", [])
            if unexplored:
                text += f"  Nearby Unexplored Tiles: {len(unexplored)}\n"
                for tile in unexplored[:5]:  # Show first 5
                    text += f"    - ({tile[0]}, {tile[1]})\n"

        text += "\nNAVIGATION MEMORY:\n"
        if pre_world or pre_starter_script:
            text += "  Not available yet. Do not treat the current coordinates as a real walkable map.\n"
        else:
            text += f"  Current Tile Visits: {navigation.get('current_visit_count', 0)}\n"
            known_exits = navigation.get("known_exits", {})
            if known_exits:
                for direction, target in known_exits.items():
                    text += f"  Known exit {direction}: ({target['x']}, {target['y']})\n"
            else:
                text += "  Known exits from current tile: none yet\n"

            blocked_dirs = navigation.get("blocked_directions", [])
            text += (
                f"  Known blocked directions from current tile: "
                f"{', '.join(blocked_dirs) if blocked_dirs else 'none'}\n"
            )
            adjacent_tiles = navigation.get("adjacent_tiles", {})
            if adjacent_tiles:
                for cue in self._build_navigation_decision_cues(
                    state,
                    navigation,
                    vision_hints,
                ):
                    text += cue + "\n"
                vision_blocked = {
                    str(direction or "").strip().lower()
                    for direction in vision_hints.get("blocked_directions", []) or []
                }
                vision_unsafe = {
                    str(direction or "").strip().lower()
                    for direction in vision_hints.get("unsafe_directions", []) or []
                }
                vision_walkable = {
                    str(direction or "").strip().lower()
                    for direction in vision_hints.get("walkable_directions", []) or []
                }
                text += (
                    "  Adjacent Tile Occupancy: "
                    "known_exit=previously succeeded, frontier=unexplored adjacent tile, "
                    "confirmed_blocked=failed 2+ times, blocked_once=failed once, "
                    "adjacent_explored=neighbor explored but this step unconfirmed, "
                    "unknown=no reliable memory yet\n"
                )
                for direction in ("up", "down", "left", "right"):
                    info = adjacent_tiles.get(direction) or {}
                    target = info.get("target") or {}
                    details = []
                    blocked_attempts = int(info.get("blocked_attempts", 0) or 0)
                    target_visit_count = int(info.get("target_visit_count", 0) or 0)
                    if blocked_attempts:
                        details.append(f"blocked_attempts={blocked_attempts}")
                    if target_visit_count:
                        details.append(f"visits={target_visit_count}")
                    if info.get("target_is_warp"):
                        details.append("warp_tile")
                    if info.get("is_preferred_frontier_step"):
                        details.append("preferred_frontier_step")
                    if direction in vision_blocked:
                        details.append("vision=blocked")
                    elif direction in vision_unsafe:
                        details.append("vision=unsafe")
                    elif direction in vision_walkable:
                        details.append("vision=walkable")
                    detail_text = " ".join(details)
                    text += (
                        f"    - {direction}: status={info.get('status', 'unknown')} "
                        f"target=({target.get('x', '?')}, {target.get('y', '?')})"
                        f"{' ' + detail_text if detail_text else ''}\n"
                    )
            text += f"  Reachable frontier tiles on this map: {navigation.get('frontier_count', 0)}\n"

            nearest_frontier = navigation.get("nearest_frontier")
            if nearest_frontier:
                frontier_target = nearest_frontier.get("target")
                frontier_path = nearest_frontier.get("path", [])
                frontier_unknown = ", ".join(nearest_frontier.get("unknown_directions", [])) or "none"
                frontier_novelty = nearest_frontier.get("novelty_label", "unknown")
                text += f"  Suggested frontier target: {frontier_target}\n"
                text += f"  Suggested route to frontier: {', '.join(frontier_path) if frontier_path else 'already there'}\n"
                text += f"  Unknown directions from frontier: {frontier_unknown}\n"
                text += (
                    f"  Frontier novelty: {frontier_novelty}; local revisit pressure "
                    f"{nearest_frontier.get('local_visit_pressure', 0)}; "
                    f"global novelty distance {nearest_frontier.get('global_novelty_distance', 0)}; "
                    f"priority score {nearest_frontier.get('priority_score', 0.0)}\n"
                )

            frontier_candidates = navigation.get("frontier_candidates", [])
            if frontier_candidates:
                text += "  Top Frontier Alternatives:\n"
                for item in frontier_candidates[:3]:
                    unknown = ", ".join(item.get("unknown_directions", [])) or "none"
                    text += (
                        f"    - {item.get('target')} novelty={item.get('novelty_label', 'unknown')} "
                        f"pressure={item.get('local_visit_pressure', 0)} "
                        f"distance={item.get('distance', '?')} "
                        f"unknown={unknown}\n"
                    )

            warp_cautions = navigation.get("warp_cautions", []) or []
            for caution in warp_cautions[:2]:
                destination = caution.get("destination") or {}
                target = caution.get("target") or {}
                if destination:
                    text += (
                        "  Warp caution: "
                        f"{caution.get('direction', '?')} reaches known warp tile "
                        f"({target.get('x', '?')}, {target.get('y', '?')}) -> "
                        f"map {destination.get('map_id', '?')} "
                        f"({destination.get('x', '?')}, {destination.get('y', '?')}); "
                        "do not step on it unless you intentionally want to change maps.\n"
                    )
                else:
                    text += (
                        "  Warp caution: "
                        f"{caution.get('direction', '?')} is a known adjacent warp tile; "
                        "do not step on it unless you intentionally want to change maps.\n"
                    )

            current_tile_warp = navigation.get("current_tile_warp") or {}
            if current_tile_warp:
                destination = current_tile_warp.get("destination") or {}
                source = current_tile_warp.get("source") or {}
                trigger_action = str(
                    current_tile_warp.get("trigger_action") or ""
                ).strip().lower()
                trigger_action_source = str(
                    current_tile_warp.get("trigger_action_source") or ""
                ).strip().lower()
                if destination:
                    text += (
                        "  Current-tile warp caution: "
                        f"you are standing on known warp source "
                        f"({source.get('x', '?')}, {source.get('y', '?')}) -> "
                        f"map {destination.get('map_id', '?')} "
                        f"({destination.get('x', '?')}, {destination.get('y', '?')})"
                    )
                else:
                    text += "  Current-tile warp caution: you are standing on a known warp source tile"
                if trigger_action:
                    if trigger_action_source == "inferred":
                        text += (
                            f"; the likely trigger action is {trigger_action} because other local moves already failed. "
                            "Step off this tile before probing unknown directions.\n"
                        )
                    else:
                        text += (
                            f"; the learned trigger action is {trigger_action}. "
                            "Step off this tile before probing unknown directions.\n"
                        )
                else:
                    text += (
                        "; the exact trigger action is not yet confirmed. "
                        "Step off this tile carefully instead of blindly probing unknown directions.\n"
                    )

            frontier_guidance = navigation.get("frontier_guidance", {}) or {}
            if frontier_guidance.get("prefer_leave_current_frontier"):
                text += (
                    "  Frontier caution: "
                    f"{frontier_guidance.get('summary', 'Current local frontier looks weak; leave it.')}\n"
                )

            local_map = navigation.get("local_map", [])
            if local_map:
                text += "  Local Map Window:\n"
                for row in local_map[:11]:
                    text += f"    {row}\n"

            map_snapshot = navigation.get("map_snapshot") or {}
            if map_snapshot.get("available"):
                text += "  Explored Map Snapshot:\n"
                bounds = map_snapshot.get("bounds") or {}
                text += (
                    "    Legend: P=player .=explored F=frontier #=confirmed-wall "
                    "W=warp ?=unknown\n"
                )
                text += (
                    f"    Bounds: x={bounds.get('min_x', '?')}..{bounds.get('max_x', '?')} "
                    f"y={bounds.get('min_y', '?')}..{bounds.get('max_y', '?')} "
                    f"size={bounds.get('width', '?')}x{bounds.get('height', '?')} "
                    f"explored={map_snapshot.get('explored_count', 0)} "
                    f"frontier={map_snapshot.get('frontier_count', 0)} "
                    f"blocked={map_snapshot.get('blocked_count', 0)} "
                    f"warps={map_snapshot.get('warp_count', 0)}\n"
                )
                for row in map_snapshot.get("prompt_rows", map_snapshot.get("rows", []))[:18]:
                    text += f"    {row}\n"

        text += "\n" + "=" * 50 + "\n"

        return text

    def get_simple_state(self) -> Dict[str, Any]:
        """Get simplified state for quick checks."""
        memory_state = self.memory_reader.get_game_state_summary()

        return {
            "turn": self.turn_count,
            "position": memory_state["position"],
            "badge_count": memory_state["badge_count"],
            "party_count": len(memory_state["party"]),
            "in_battle": memory_state["in_battle"],
        }

    def _get_visual_analysis(self, screen_image) -> Dict[str, Any]:
        """Return either real visual analysis or a memory-only placeholder."""
        if self.visual_enabled and self.vision:
            try:
                analysis = self.vision.analyze_screen(screen_image)
                if isinstance(analysis, dict):
                    analysis.setdefault("local_analysis_enabled", True)
                return analysis
            except Exception as exc:
                self.logger.warning(
                    f"Visual analysis failed, falling back to memory-only: {exc}"
                )

        return {
            "screen_type": "unknown",
            "description": "Harness-side pixel heuristics are disabled. The raw screenshot is still attached separately for model vision.",
            "screen_size": (screen_image.width, screen_image.height)
            if screen_image
            else None,
            "frame_number": self.turn_count,
            "local_analysis_enabled": False,
        }

    def _compute_memory_deltas(self, memory_state: Dict[str, Any]) -> Dict[str, Any]:
        """Compare current and last memory state to surface deltas for the LLM."""
        if not self._last_memory_state:
            return {
                "position_changed": True,
                "money_delta": 0,
                "battle_toggled": False,
                "movement_stall_turns": 0,
                "stuck_hint": "unknown",
            }

        last_pos = self._last_memory_state["position"]
        pos = memory_state["position"]
        position_changed = (
            last_pos["x"],
            last_pos["y"],
            last_pos["map_id"],
        ) != (pos["x"], pos["y"], pos["map_id"])

        money_delta = memory_state["money"] - self._last_memory_state["money"]
        battle_toggled = memory_state["in_battle"] != self._last_memory_state["in_battle"]
        ui_state = memory_state.get("ui", {})
        text_or_menu_active = bool(ui_state.get("text_box_active") or ui_state.get("menu_active"))

        if not position_changed and not memory_state["in_battle"] and not text_or_menu_active:
            self._movement_stall_turns += 1
        else:
            self._movement_stall_turns = 0

        if text_or_menu_active:
            stuck_hint = "ui text or menu is active; lack of movement is expected"
        elif self._movement_stall_turns >= 2:
            stuck_hint = "possibly stuck - explore a different direction or unseen tile"
        else:
            stuck_hint = "moving or in battle"

        if (
            not position_changed
            and not memory_state["in_battle"]
            and not text_or_menu_active
            and self._movement_stall_turns < 2
        ):
            stuck_hint = "slight stall"

        return {
            "position_changed": position_changed,
            "money_delta": money_delta,
            "battle_toggled": battle_toggled,
            "movement_stall_turns": self._movement_stall_turns,
            "stuck_hint": stuck_hint,
        }

    def _update_position_history(self, position: Dict[str, int]) -> None:
        """Track recent positions to detect repeated states."""
        self._position_history.append(position.copy())
        if len(self._position_history) > 10:
            self._position_history.pop(0)

    def _analyze_recent_movement(self, memory_state: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize recent same-map movement so the AI can notice local loops."""
        position = memory_state.get("position", {}) or {}
        map_id = int(position.get("map_id", -1) or -1)
        x = int(position.get("x", 0) or 0)
        y = int(position.get("y", 0) or 0)

        same_map_positions: List[Dict[str, int]] = []
        for item in reversed(self._position_history):
            if int(item.get("map_id", -1) or -1) != map_id:
                break
            same_map_positions.append(item)
            if len(same_map_positions) >= 10:
                break

        same_map_positions.reverse()
        coords = [
            (int(item.get("x", 0) or 0), int(item.get("y", 0) or 0))
            for item in same_map_positions
        ]
        if not coords:
            return {
                "window_size": 0,
                "unique_tiles": 0,
                "bounding_box_width": 0,
                "bounding_box_height": 0,
                "current_tile_repeat_count": 0,
                "micro_loop_warning": False,
                "warning": None,
            }

        unique_tiles = len(set(coords))
        min_x = min(px for px, _ in coords)
        max_x = max(px for px, _ in coords)
        min_y = min(py for _, py in coords)
        max_y = max(py for _, py in coords)
        width = max_x - min_x + 1
        height = max_y - min_y + 1
        current_repeats = sum(1 for px, py in coords if (px, py) == (x, y))
        micro_loop_warning = (
            len(coords) >= 6
            and unique_tiles <= 4
            and width <= 2
            and height <= 2
        )
        warning = None
        if micro_loop_warning:
            warning = (
                f"high - last {len(coords)} same-map positions stayed within a "
                f"{width}x{height} box covering only {unique_tiles} tiles"
            )

        return {
            "window_size": len(coords),
            "unique_tiles": unique_tiles,
            "bounding_box_width": width,
            "bounding_box_height": height,
            "current_tile_repeat_count": current_repeats,
            "micro_loop_warning": micro_loop_warning,
            "warning": warning,
        }

    def _analyze_battle_state(self, memory_state: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize reliable battle-phase signals for prompt consumption."""
        battle = memory_state.get("battle", {}) or {}
        party = list(memory_state.get("party", []) or [])
        ui_state = memory_state.get("ui", {}) or {}
        last_memory = self._last_memory_state or {}
        last_battle = last_memory.get("battle", {}) or {}

        in_battle = bool(memory_state.get("in_battle"))
        last_in_battle = bool(last_memory.get("in_battle"))
        current_signature = (
            battle.get("battle_type"),
            battle.get("enemy_species"),
            battle.get("enemy_level"),
        )
        last_signature = (
            last_battle.get("battle_type"),
            last_battle.get("enemy_species"),
            last_battle.get("enemy_level"),
        )
        same_battle = in_battle and last_in_battle and current_signature == last_signature

        lead_summary = None
        if party:
            lead = party[0]
            max_hp = int(lead.get("max_hp", 0) or 0)
            current_hp = int(lead.get("current_hp", 0) or 0)
            hp_percent = (current_hp / max_hp * 100.0) if max_hp > 0 else 0.0
            lead_summary = {
                "species": lead.get("species", "Unknown"),
                "level": int(lead.get("level", 0) or 0),
                "current_hp": current_hp,
                "max_hp": max_hp,
                "hp_percent": round(hp_percent, 1),
            }

        encounter_type = battle.get("battle_type", "none")
        enemy_hp_changed = False
        focus_hint = None

        if in_battle:
            if same_battle:
                self._battle_turns += 1
            else:
                self._battle_turns = 1

            current_enemy_hp = battle.get("enemy_current_hp")
            last_enemy_hp = last_battle.get("enemy_current_hp")
            enemy_hp_changed = bool(
                same_battle
                and current_enemy_hp is not None
                and last_enemy_hp is not None
                and int(current_enemy_hp) != int(last_enemy_hp)
            )

            if same_battle and not enemy_hp_changed:
                self._battle_stall_turns += 1
            else:
                self._battle_stall_turns = 0

            phase = "entered_battle" if not same_battle else "battle_in_progress"
            if encounter_type == "trainer":
                focus_hint = "A trainer battle is active. Finish the encounter instead of trying to walk."
            else:
                focus_hint = "A battle is active. Resolve the fight before returning to movement goals."
            if lead_summary and float(lead_summary.get("hp_percent", 0.0) or 0.0) <= 25.0:
                focus_hint += " Your lead Pokemon is low HP, so avoid random menuing."
            if self._battle_stall_turns >= 3:
                focus_hint = (
                    "Battle progress has stalled for several turns. Re-check the screenshot "
                    "instead of repeating the same guess."
                )
        else:
            self._battle_turns = 0
            self._battle_stall_turns = 0
            if last_in_battle and ui_state.get("text_box_active"):
                encounter_type = last_battle.get("battle_type", "unknown")
                phase = "post_battle_dialogue"
                focus_hint = (
                    "The battle flag just dropped but result dialogue is still active. "
                    "Finish the text before resuming movement."
                )
            elif last_in_battle:
                encounter_type = last_battle.get("battle_type", "unknown")
                phase = "battle_just_ended"
                focus_hint = (
                    "The battle just ended. Verify the current screen before assuming "
                    "normal exploration has resumed."
                )
            else:
                encounter_type = "none"
                phase = "not_in_battle"

        return {
            "active": in_battle,
            "phase": phase,
            "encounter_type": encounter_type,
            "battle_turns": self._battle_turns,
            "enemy_hp_changed": enemy_hp_changed,
            "battle_stall_turns": self._battle_stall_turns,
            "enemy_species": battle.get("enemy_species") if in_battle else last_battle.get("enemy_species"),
            "enemy_level": battle.get("enemy_level") if in_battle else last_battle.get("enemy_level"),
            "enemy_current_hp": battle.get("enemy_current_hp") if in_battle else last_battle.get("enemy_current_hp"),
            "lead_pokemon": lead_summary,
            "focus_hint": focus_hint,
        }
