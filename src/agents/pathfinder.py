"""Pathfinder agent for complex navigation."""

from typing import List, Tuple, Optional
from anthropic import Anthropic

from ..utils.logger import get_logger
from ..utils.config import get_config


class PathfinderAgent:
    """Specialized agent for pathfinding and navigation."""

    SYSTEM_PROMPT = """You are a pathfinding specialist for Pokemon Red. Your task is to find optimal routes from point A to point B.

Given:
- Start position (map_id, x, y)
- Target position (map_id, x, y)
- Map of explored tiles
- Known obstacles

Your task:
1. If on same map: Plan a sequence of moves (up/down/left/right) to reach target
2. If on different maps: Identify which exits/doors to use to reach target map
3. Avoid obstacles and previously stuck positions
4. Use A* or similar pathfinding when possible

Response format:
ANALYSIS: <your pathfinding analysis>
PATH: <comma-separated list of moves, e.g., "up,up,right,right,up">
"""

    def __init__(self):
        """Initialize pathfinder agent."""
        self.logger = get_logger('Pathfinder')
        self.config = get_config()

        # Initialize AI client with custom base_url if provided
        import os
        base_url = os.getenv('ANTHROPIC_BASE_URL')
        if base_url:
            self.client = Anthropic(base_url=base_url)
        else:
            self.client = Anthropic()

        self.model = self.config.get('ai.agents.pathfinder.model')
        self.temperature = self.config.get('ai.agents.pathfinder.temperature')

        self.logger.info("Pathfinder agent initialized")

    def find_path(self, start: Tuple[int, int, int], target: Tuple[int, int, int],
                  explored_tiles: List[Tuple[int, int]]) -> Optional[List[str]]:
        """Find path from start to target.

        Args:
            start: (map_id, x, y)
            target: (map_id, x, y)
            explored_tiles: List of explored (x, y) positions on current map

        Returns:
            List of actions, or None if no path found
        """
        self.logger.info(f"Finding path from {start} to {target}")

        # Build prompt
        prompt = f"""Find a path from {start} to {target}.

Start: Map {start[0]}, Position ({start[1]}, {start[2]})
Target: Map {target[0]}, Position ({target[1]}, {target[2]})

Explored tiles on current map: {len(explored_tiles)} tiles

Plan a path and provide the sequence of moves."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=self.temperature,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Parse path
            path = self._parse_path(response_text)

            if path:
                self.logger.info(f"Found path with {len(path)} moves")
            else:
                self.logger.warning("No path found")

            return path

        except Exception as e:
            self.logger.error(f"Pathfinding failed: {e}")
            return None

    def _parse_path(self, response: str) -> Optional[List[str]]:
        """Parse path from response.

        Args:
            response: AI response

        Returns:
            List of moves
        """
        for line in response.split('\n'):
            if line.strip().startswith('PATH:'):
                path_str = line.replace('PATH:', '').strip()
                moves = [m.strip().lower() for m in path_str.split(',')]
                # Validate moves
                valid_moves = ['up', 'down', 'left', 'right']
                moves = [m for m in moves if m in valid_moves]
                return moves if moves else None

        return None
