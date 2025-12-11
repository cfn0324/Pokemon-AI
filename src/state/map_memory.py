"""Map memory system with fog-of-war tracking."""

import json
from typing import Dict, List, Tuple, Set, Any
from pathlib import Path
from collections import defaultdict

from ..utils.logger import get_logger


class MapMemory:
    """Tracks explored areas with fog-of-war system."""

    def __init__(self, save_dir: str = "data/maps"):
        """Initialize map memory.

        Args:
            save_dir: Directory to save map data
        """
        self.logger = get_logger('MapMemory')
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # Map ID -> Set of (x, y) tuples for explored tiles
        self.explored_tiles: Dict[int, Set[Tuple[int, int]]] = defaultdict(set)

        # Map ID -> Dict of map properties
        self.map_properties: Dict[int, Dict[str, Any]] = {}

        # Current position
        self.current_map = None
        self.current_position = None

        self.load()

        self.logger.info("Map memory initialized")

    def update_position(self, map_id: int, x: int, y: int) -> None:
        """Update current position and mark as explored.

        Args:
            map_id: Current map ID
            x: X coordinate
            y: Y coordinate
        """
        self.current_map = map_id
        self.current_position = (x, y)

        # Mark current tile as explored
        self.explored_tiles[map_id].add((x, y))

        # Also mark adjacent tiles as visible (but not necessarily explored)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                adj_x, adj_y = x + dx, y + dy
                # Don't mark as fully explored, just visible
                # This creates a fog-of-war effect

    def is_tile_explored(self, map_id: int, x: int, y: int) -> bool:
        """Check if a tile has been explored.

        Args:
            map_id: Map ID
            x: X coordinate
            y: Y coordinate

        Returns:
            True if explored
        """
        return (x, y) in self.explored_tiles.get(map_id, set())

    def get_explored_tiles(self, map_id: int) -> List[Tuple[int, int]]:
        """Get all explored tiles for a map.

        Args:
            map_id: Map ID

        Returns:
            List of (x, y) tuples
        """
        return list(self.explored_tiles.get(map_id, set()))

    def get_unexplored_adjacent(self, map_id: int, x: int, y: int,
                                radius: int = 5) -> List[Tuple[int, int]]:
        """Get unexplored tiles near a position.

        Args:
            map_id: Map ID
            x: Center X coordinate
            y: Center Y coordinate
            radius: Search radius

        Returns:
            List of unexplored (x, y) positions
        """
        unexplored = []
        explored_set = self.explored_tiles.get(map_id, set())

        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                pos = (x + dx, y + dy)
                if pos not in explored_set:
                    # Basic bounds check (maps are typically 0-255)
                    if 0 <= pos[0] <= 255 and 0 <= pos[1] <= 255:
                        unexplored.append(pos)

        # Sort by distance from current position
        unexplored.sort(key=lambda p: abs(p[0] - x) + abs(p[1] - y))

        return unexplored

    def get_exploration_status(self, map_id: int) -> Dict[str, Any]:
        """Get exploration statistics for a map.

        Args:
            map_id: Map ID

        Returns:
            Dict with exploration stats
        """
        explored = self.explored_tiles.get(map_id, set())
        nearby_unexplored = []

        if self.current_map == map_id and self.current_position:
            nearby_unexplored = self.get_unexplored_adjacent(
                map_id,
                self.current_position[0],
                self.current_position[1],
                radius=5
            )

        # Estimate total tiles (typical Pokemon Red map is 10x9 to 20x18)
        # We'll use explored count as a lower bound
        estimated_total = max(len(explored), 200)  # Rough estimate

        return {
            'map_id': map_id,
            'explored_count': len(explored),
            'total_tiles': estimated_total,
            'exploration_percent': len(explored) / estimated_total * 100,
            'nearby_unexplored': nearby_unexplored[:10],  # Top 10 nearest
        }

    def get_all_explored_maps(self) -> List[int]:
        """Get list of all explored map IDs.

        Returns:
            List of map IDs
        """
        return list(self.explored_tiles.keys())

    def save(self) -> None:
        """Save map memory to disk."""
        save_file = self.save_dir / "map_memory.json"

        # Convert sets to lists for JSON serialization
        data = {
            'explored_tiles': {
                str(map_id): [list(pos) for pos in tiles]
                for map_id, tiles in self.explored_tiles.items()
            },
            'map_properties': self.map_properties,
        }

        with open(save_file, 'w') as f:
            json.dump(data, f, indent=2)

        self.logger.debug(f"Saved map memory to {save_file}")

    def load(self) -> None:
        """Load map memory from disk."""
        save_file = self.save_dir / "map_memory.json"

        if not save_file.exists():
            self.logger.info("No saved map memory found, starting fresh")
            return

        try:
            with open(save_file, 'r') as f:
                data = json.load(f)

            # Convert lists back to sets
            self.explored_tiles = defaultdict(set)
            for map_id_str, tiles in data.get('explored_tiles', {}).items():
                map_id = int(map_id_str)
                self.explored_tiles[map_id] = set(tuple(pos) for pos in tiles)

            self.map_properties = data.get('map_properties', {})

            self.logger.info(f"Loaded map memory: {len(self.explored_tiles)} maps explored")

        except Exception as e:
            self.logger.error(f"Failed to load map memory: {e}")

    def reset_map(self, map_id: int) -> None:
        """Reset exploration for a specific map.

        Args:
            map_id: Map ID to reset
        """
        if map_id in self.explored_tiles:
            del self.explored_tiles[map_id]
        self.logger.info(f"Reset exploration for map {map_id}")

    def reset_all(self) -> None:
        """Reset all exploration data."""
        self.explored_tiles.clear()
        self.map_properties.clear()
        self.logger.info("Reset all map memory")
