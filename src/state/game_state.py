"""Game state processor combining memory data (visual optional)."""

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
        vision_processor: VisionProcessor,
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

    def update(self, screen_image=None) -> Dict[str, Any]:
        """Update and return current game state."""
        self.turn_count += 1
        self.last_update = datetime.now()

        # Get memory data
        memory_state = self.memory_reader.get_game_state_summary()
        deltas = self._compute_memory_deltas(memory_state)

        # Get visual analysis or placeholder
        if screen_image is None:
            screen_image = self.emulator.get_screen_image()
        visual_analysis = self._get_visual_analysis(screen_image)

        # Update map memory
        position = memory_state["position"]
        self.map_memory.update_position(position["map_id"], position["x"], position["y"])
        self._update_position_history(position)

        # Get explored/unexplored tiles
        exploration = self.map_memory.get_exploration_status(position["map_id"])

        # Combine into comprehensive state
        state = {
            "turn": self.turn_count,
            "timestamp": self.last_update.isoformat(),
            "memory": memory_state,
            "visual": visual_analysis,
            "exploration": exploration,
            "map_memory": {
                "current_map": position["map_id"],
                "explored_tiles": exploration["explored_count"],
                "total_tiles": exploration["total_tiles"],
                "exploration_percent": exploration["exploration_percent"],
            },
            "deltas": deltas,
        }

        self._last_memory_state = memory_state
        self.logger.state("full_state", state)

        return state

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

        text = f"""=== GAME STATE (Turn {state['turn']}) ===

POSITION:
- Map ID: {position['map_id']}
- Coordinates: ({position['x']}, {position['y']})
- Vision Mode: {visual.get('screen_type', 'memory_only')}

BADGES: {memory['badge_count']}/8
"""
        for badge_name, obtained in badges.items():
            status = "[X]" if obtained else "[ ]"
            text += f"  {status} {badge_name}\n"

        text += f"\nMONEY: ${memory['money']}\n"

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

        # Memory-only deltas to help the LLM detect being stuck
        text += "\nSTATE DELTAS (memory-based):\n"
        text += f"  Position changed: {deltas.get('position_changed', False)}\n"
        text += f"  Money delta: {deltas.get('money_delta', 0)}\n"
        text += f"  Battle toggled: {deltas.get('battle_toggled', False)}\n"
        text += f"  Stuck hint: {deltas.get('stuck_hint', 'unknown')}\n"

        # Exploration info
        text += f"\nEXPLORATION:\n"
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
                return self.vision.analyze_screen(screen_image)
            except Exception as exc:
                self.logger.warning(
                    f"Visual analysis failed, falling back to memory-only: {exc}"
                )

        return {
            "screen_type": "memory_only",
            "description": "Pixel vision disabled; using memory-only perception",
            "screen_size": (screen_image.width, screen_image.height)
            if screen_image
            else None,
            "frame_number": self.turn_count,
        }

    def _compute_memory_deltas(self, memory_state: Dict[str, Any]) -> Dict[str, Any]:
        """Compare current and last memory state to surface deltas for the LLM."""
        if not self._last_memory_state:
            return {
                "position_changed": True,
                "money_delta": 0,
                "battle_toggled": False,
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

        stuck_hint = (
            "possibly stuck"
            if (not position_changed and not memory_state["in_battle"])
            else "moving or in battle"
        )
        return {
            "position_changed": position_changed,
            "money_delta": money_delta,
            "battle_toggled": battle_toggled,
            "stuck_hint": stuck_hint,
        }

    def _update_position_history(self, position: Dict[str, int]) -> None:
        """Track recent positions to detect repeated states."""
        self._position_history.append(position.copy())
        if len(self._position_history) > 10:
            self._position_history.pop(0)
