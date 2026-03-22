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
        self._phase_hint: Optional[str] = None
        self._pre_starter_script_latched = False

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
            text += f"  Reachable frontier tiles on this map: {navigation.get('frontier_count', 0)}\n"

            nearest_frontier = navigation.get("nearest_frontier")
            if nearest_frontier:
                frontier_target = nearest_frontier.get("target")
                frontier_path = nearest_frontier.get("path", [])
                frontier_unknown = ", ".join(nearest_frontier.get("unknown_directions", [])) or "none"
                text += f"  Suggested frontier target: {frontier_target}\n"
                text += f"  Suggested route to frontier: {', '.join(frontier_path) if frontier_path else 'already there'}\n"
                text += f"  Unknown directions from frontier: {frontier_unknown}\n"

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
