"""Puzzle solver agent for boulder puzzles and complex challenges."""

from typing import Dict, Any, Optional, List
from anthropic import Anthropic

from ..utils.logger import get_logger
from ..utils.config import get_config


class PuzzleSolverAgent:
    """Specialized agent for solving puzzles like boulder-switch puzzles."""

    SYSTEM_PROMPT = """You are a puzzle-solving specialist for Pokemon Red. You excel at solving:

1. Boulder (Strength) puzzles - Sokoban-style push puzzles
2. Switch/button puzzles
3. Ice slide puzzles
4. Complex maze navigation

Given a puzzle state:
- Analyze the puzzle structure
- Identify the goal (e.g., all boulders on switches)
- Plan a sequence of moves to solve it

Response format:
ANALYSIS: <puzzle analysis>
SOLUTION: <comma-separated sequence of moves>
"""

    def __init__(self):
        """Initialize puzzle solver agent."""
        self.logger = get_logger('PuzzleSolver')
        self.config = get_config()

        # Initialize AI client with custom base_url if provided
        import os
        base_url = os.getenv('ANTHROPIC_BASE_URL')
        if base_url:
            self.client = Anthropic(base_url=base_url)
        else:
            self.client = Anthropic()

        self.model = self.config.get('ai.agents.puzzle_solver.model')
        self.temperature = self.config.get('ai.agents.puzzle_solver.temperature')

        self.logger.info("Puzzle solver agent initialized")

    def solve_puzzle(self, puzzle_description: str, puzzle_state: Dict[str, Any]) -> Optional[List[str]]:
        """Solve a puzzle.

        Args:
            puzzle_description: Description of the puzzle
            puzzle_state: Current state of the puzzle

        Returns:
            List of moves to solve puzzle
        """
        self.logger.info(f"Solving puzzle: {puzzle_description}")

        prompt = f"""Puzzle: {puzzle_description}

Current state: {puzzle_state}

Provide a solution as a sequence of moves."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=3000,
                temperature=self.temperature,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            solution = self._parse_solution(response_text)

            if solution:
                self.logger.info(f"Found solution with {len(solution)} moves")
            else:
                self.logger.warning("No solution found")

            return solution

        except Exception as e:
            self.logger.error(f"Puzzle solving failed: {e}")
            return None

    def _parse_solution(self, response: str) -> Optional[List[str]]:
        """Parse solution from response.

        Args:
            response: AI response

        Returns:
            List of moves
        """
        for line in response.split('\n'):
            if line.strip().startswith('SOLUTION:'):
                solution_str = line.replace('SOLUTION:', '').strip()
                moves = [m.strip().lower() for m in solution_str.split(',')]
                # Validate moves
                valid_moves = ['up', 'down', 'left', 'right', 'a', 'b']
                moves = [m for m in moves if m in valid_moves]
                return moves if moves else None

        return None
