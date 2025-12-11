"""Progress tracker for monitoring game advancement."""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from pathlib import Path

from ..utils.logger import get_logger


class ProgressTracker:
    """Tracks overall game progress and milestones."""

    def __init__(self, save_dir: str = "data/checkpoints"):
        """Initialize progress tracker.

        Args:
            save_dir: Directory to save progress data
        """
        self.logger = get_logger('ProgressTracker')
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # Milestones
        self.badges_earned: List[str] = []
        self.pokemon_caught: List[str] = []
        self.key_items_obtained: List[str] = []
        self.gyms_defeated: List[str] = []
        self.elite_four_defeated: bool = False
        self.champion_defeated: bool = False

        # Statistics
        self.total_turns = 0
        self.total_battles = 0
        self.total_distance_traveled = 0
        self.start_time = datetime.now()

        # Turn markers for major events
        self.milestone_turns: Dict[str, int] = {}

        self.logger.info("Progress tracker initialized")

    def update(self, turn: int, game_state: Dict[str, Any]) -> None:
        """Update progress based on current game state.

        Args:
            turn: Current turn number
            game_state: Game state dict
        """
        self.total_turns = turn

        # Check badges
        badges = game_state.get('memory', {}).get('badges', {})
        for badge_name, obtained in badges.items():
            if obtained and badge_name not in self.badges_earned:
                self.badges_earned.append(badge_name)
                self.milestone_turns[f"badge_{badge_name}"] = turn
                self.logger.milestone(f"EARNED BADGE: {badge_name} (Turn {turn})")

        # Check party for new Pokemon
        party = game_state.get('memory', {}).get('party', [])
        for pokemon in party:
            species = pokemon.get('species', 'Unknown')
            if species not in self.pokemon_caught:
                self.pokemon_caught.append(species)
                self.logger.info(f"New Pokemon: {species}")

    def get_progress_summary(self) -> str:
        """Get formatted progress summary.

        Returns:
            Progress summary text
        """
        elapsed = datetime.now() - self.start_time
        hours = elapsed.total_seconds() / 3600

        summary = f"""=== PROGRESS SUMMARY ===
Time Elapsed: {hours:.1f} hours
Total Turns: {self.total_turns}

Badges: {len(self.badges_earned)}/8
{', '.join(self.badges_earned) if self.badges_earned else 'None yet'}

Pokemon Caught: {len(self.pokemon_caught)}
{', '.join(self.pokemon_caught[:10])}{'...' if len(self.pokemon_caught) > 10 else ''}

"""
        if self.milestone_turns:
            summary += "Major Milestones:\n"
            for milestone, turn in sorted(self.milestone_turns.items(), key=lambda x: x[1]):
                summary += f"  {milestone}: Turn {turn}\n"

        return summary

    def get_completion_percentage(self) -> float:
        """Estimate game completion percentage.

        Returns:
            Completion percentage (0-100)
        """
        # Simple heuristic based on badges
        badge_progress = len(self.badges_earned) / 8 * 80  # Badges = 80%

        # Elite Four = 15%
        elite_four_progress = 15 if self.elite_four_defeated else 0

        # Champion = 5%
        champion_progress = 5 if self.champion_defeated else 0

        return min(100, badge_progress + elite_four_progress + champion_progress)

    def save(self, filepath: Optional[str] = None) -> None:
        """Save progress to file.

        Args:
            filepath: Path to save file (default: auto-generated)
        """
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = str(self.save_dir / f"progress_{timestamp}.json")

        data = {
            'badges_earned': self.badges_earned,
            'pokemon_caught': self.pokemon_caught,
            'key_items': self.key_items_obtained,
            'gyms_defeated': self.gyms_defeated,
            'elite_four_defeated': self.elite_four_defeated,
            'champion_defeated': self.champion_defeated,
            'total_turns': self.total_turns,
            'total_battles': self.total_battles,
            'milestone_turns': self.milestone_turns,
            'start_time': self.start_time.isoformat(),
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        self.logger.info(f"Saved progress to {filepath}")

    def load(self, filepath: str) -> None:
        """Load progress from file.

        Args:
            filepath: Path to load from
        """
        if not Path(filepath).exists():
            self.logger.warning(f"Progress file not found: {filepath}")
            return

        with open(filepath, 'r') as f:
            data = json.load(f)

        self.badges_earned = data.get('badges_earned', [])
        self.pokemon_caught = data.get('pokemon_caught', [])
        self.key_items_obtained = data.get('key_items', [])
        self.gyms_defeated = data.get('gyms_defeated', [])
        self.elite_four_defeated = data.get('elite_four_defeated', False)
        self.champion_defeated = data.get('champion_defeated', False)
        self.total_turns = data.get('total_turns', 0)
        self.total_battles = data.get('total_battles', 0)
        self.milestone_turns = data.get('milestone_turns', {})

        start_time_str = data.get('start_time')
        if start_time_str:
            self.start_time = datetime.fromisoformat(start_time_str)

        self.logger.info(f"Loaded progress from {filepath}")
