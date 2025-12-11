"""Game state processor combining memory and vision data."""

from typing import Dict, Any, Optional
from datetime import datetime

from ..emulator.game_boy import GameBoyEmulator
from ..emulator.memory_reader import MemoryReader
from .vision import VisionProcessor
from .map_memory import MapMemory
from ..utils.logger import get_logger


class GameState:
    """Comprehensive game state representation."""

    def __init__(self, emulator: GameBoyEmulator, memory_reader: MemoryReader,
                 vision_processor: VisionProcessor, map_memory: MapMemory):
        """Initialize game state processor.

        Args:
            emulator: GameBoy emulator instance
            memory_reader: Memory reader instance
            vision_processor: Vision processor instance
            map_memory: Map memory instance
        """
        self.emulator = emulator
        self.memory_reader = memory_reader
        self.vision = vision_processor
        self.map_memory = map_memory
        self.logger = get_logger('GameState')

        self.turn_count = 0
        self.last_update = None

    def update(self) -> Dict[str, Any]:
        """Update and return current game state.

        Returns:
            Comprehensive game state dict
        """
        self.turn_count += 1
        self.last_update = datetime.now()

        # Get memory data
        memory_state = self.memory_reader.get_game_state_summary()

        # Get visual analysis
        screen_image = self.emulator.get_screen_image()
        visual_analysis = self.vision.analyze_screen(screen_image)

        # Update map memory
        position = memory_state['position']
        self.map_memory.update_position(position['map_id'], position['x'], position['y'])

        # Get explored/unexplored tiles
        exploration = self.map_memory.get_exploration_status(position['map_id'])

        # Combine into comprehensive state
        state = {
            'turn': self.turn_count,
            'timestamp': self.last_update.isoformat(),
            'memory': memory_state,
            'visual': visual_analysis,
            'exploration': exploration,
            'map_memory': {
                'current_map': position['map_id'],
                'explored_tiles': exploration['explored_count'],
                'total_tiles': exploration['total_tiles'],
                'exploration_percent': exploration['exploration_percent'],
            }
        }

        self.logger.state('full_state', state)

        return state

    def get_text_representation(self, state: Optional[Dict[str, Any]] = None) -> str:
        """Convert game state to text representation for AI.

        Args:
            state: Game state dict (uses last state if None)

        Returns:
            Text representation of game state
        """
        if state is None:
            state = self.update()

        memory = state['memory']
        position = memory['position']
        badges = memory['badges']
        party = memory['party']
        visual = state['visual']

        text = f"""=== GAME STATE (Turn {state['turn']}) ===

POSITION:
- Map ID: {position['map_id']}
- Coordinates: ({position['x']}, {position['y']})
- Grid Position: {visual.get('grid_position', 'N/A')}

BADGES: {memory['badge_count']}/8
"""
        for badge_name, obtained in badges.items():
            status = "[X]" if obtained else "[ ]"
            text += f"  {status} {badge_name}\n"

        text += f"\nMONEY: ${memory['money']}\n"

        text += f"\nPARTY: {len(party)} Pokemon\n"
        for i, pokemon in enumerate(party, 1):
            hp_percent = (pokemon['current_hp'] / pokemon['max_hp'] * 100) if pokemon['max_hp'] > 0 else 0
            text += f"  {i}. {pokemon['species']} Lv.{pokemon['level']} - HP: {pokemon['current_hp']}/{pokemon['max_hp']} ({hp_percent:.0f}%)\n"
            text += f"     Moves: {len(pokemon['moves'])} | "
            for move in pokemon['moves']:
                text += f"[PP:{move['pp']}] "
            text += "\n"

        if memory['in_battle']:
            text += "\n⚔️  CURRENTLY IN BATTLE\n"

        text += f"\nVISUAL ANALYSIS:\n"
        text += f"  Screen Description: {visual.get('description', 'No description')}\n"
        text += f"  Detected Elements: {', '.join(visual.get('elements', []))}\n"

        text += f"\nEXPLORATION:\n"
        text += f"  Current Map Explored: {state['map_memory']['exploration_percent']:.1f}%\n"
        text += f"  Tiles Explored: {state['map_memory']['explored_tiles']}/{state['map_memory']['total_tiles']}\n"

        unexplored = state['exploration'].get('nearby_unexplored', [])
        if unexplored:
            text += f"  Nearby Unexplored Tiles: {len(unexplored)}\n"
            for tile in unexplored[:5]:  # Show first 5
                text += f"    - ({tile[0]}, {tile[1]})\n"

        text += "\n" + "="*50 + "\n"

        return text

    def get_simple_state(self) -> Dict[str, Any]:
        """Get simplified state for quick checks.

        Returns:
            Simplified state dict
        """
        memory_state = self.memory_reader.get_game_state_summary()

        return {
            'turn': self.turn_count,
            'position': memory_state['position'],
            'badge_count': memory_state['badge_count'],
            'party_count': len(memory_state['party']),
            'in_battle': memory_state['in_battle'],
        }
