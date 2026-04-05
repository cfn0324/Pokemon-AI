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

    def __init__(
        self,
        emulator: GameBoyEmulator,
        memory_reader: MemoryReader,
        vision_processor: Optional[VisionProcessor],
        map_memory: MapMemory,
        visual_enabled: bool = False,
    ):
        """Initialize game state processor.

        Args:
            emulator: GameBoy emulator instance
            memory_reader: Memory reader instance
            vision_processor: Vision processor instance
            map_memory: Map memory instance
            visual_enabled: Whether to run pixel-level vision analysis
        """
        self.emulator = emulator
        self.memory_reader = memory_reader
        self.vision = vision_processor
        self.map_memory = map_memory
        self.visual_enabled = visual_enabled
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

        for direction in ("up", "down", "left", "right"):
            info = adjacent_tiles.get(direction) or {}
            status = str(info.get("status") or "unknown").strip().lower() or "unknown"
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
            if not preferred and not unverified:
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
        movement_pattern = self._analyze_recent_movement(memory_state)
        battle_summary = self._analyze_battle_state(memory_state)

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
            "deltas": deltas,
            "movement_pattern": movement_pattern,
            "battle_summary": battle_summary,
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
            text += "     Moves: "
            for move in pokemon["moves"]:
                text += f"[PP:{move['pp']}] "
            text += "\n"

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
