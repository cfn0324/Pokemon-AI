"""Goal manager for tracking objectives."""

from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

from ..utils.logger import get_logger


@dataclass
class Goal:
    """Represents a goal."""
    goal_type: str  # 'primary', 'secondary', 'tertiary'
    description: str
    created_at: str
    completed: bool = False
    completed_at: Optional[str] = None


class GoalManager:
    """Manages primary, secondary, and tertiary goals."""

    def __init__(self):
        """Initialize goal manager."""
        self.logger = get_logger('GoalManager')

        self.primary_goal: Optional[Goal] = None
        self.secondary_goal: Optional[Goal] = None
        self.tertiary_goal: Optional[Goal] = None

        # Goal history
        self.completed_goals: List[Goal] = []

        self.logger.info("Goal manager initialized")

    def set_primary_goal(self, description: str) -> None:
        """Set primary goal.

        Args:
            description: Goal description
        """
        # Complete old goal if exists
        if self.primary_goal and not self.primary_goal.completed:
            self.complete_goal('primary')

        self.primary_goal = Goal(
            goal_type='primary',
            description=description,
            created_at=datetime.now().isoformat()
        )

        self.logger.milestone(f"NEW PRIMARY GOAL: {description}")

    def set_secondary_goal(self, description: str) -> None:
        """Set secondary goal.

        Args:
            description: Goal description
        """
        if self.secondary_goal and not self.secondary_goal.completed:
            self.complete_goal('secondary')

        self.secondary_goal = Goal(
            goal_type='secondary',
            description=description,
            created_at=datetime.now().isoformat()
        )

        self.logger.info(f"NEW SECONDARY GOAL: {description}")

    def set_tertiary_goal(self, description: str) -> None:
        """Set tertiary goal.

        Args:
            description: Goal description
        """
        if self.tertiary_goal and not self.tertiary_goal.completed:
            self.complete_goal('tertiary')

        self.tertiary_goal = Goal(
            goal_type='tertiary',
            description=description,
            created_at=datetime.now().isoformat()
        )

        self.logger.info(f"NEW TERTIARY GOAL: {description}")

    def complete_goal(self, goal_type: str) -> None:
        """Mark a goal as completed.

        Args:
            goal_type: 'primary', 'secondary', or 'tertiary'
        """
        goal = None
        if goal_type == 'primary':
            goal = self.primary_goal
        elif goal_type == 'secondary':
            goal = self.secondary_goal
        elif goal_type == 'tertiary':
            goal = self.tertiary_goal

        if goal and not goal.completed:
            goal.completed = True
            goal.completed_at = datetime.now().isoformat()
            self.completed_goals.append(goal)

            self.logger.milestone(f"COMPLETED {goal_type.upper()} GOAL: {goal.description}")

    def get_current_goals(self) -> Dict[str, Optional[str]]:
        """Get current goals.

        Returns:
            Dict mapping goal types to descriptions
        """
        return {
            'primary': self.primary_goal.description if self.primary_goal else None,
            'secondary': self.secondary_goal.description if self.secondary_goal else None,
            'tertiary': self.tertiary_goal.description if self.tertiary_goal else None,
        }

    def get_goals_text(self) -> str:
        """Get formatted goals for AI.

        Returns:
            Formatted goals text
        """
        text = "=== CURRENT GOALS ===\n"

        if self.primary_goal:
            text += f"PRIMARY: {self.primary_goal.description}\n"
        else:
            text += "PRIMARY: Not set\n"

        if self.secondary_goal:
            text += f"SECONDARY: {self.secondary_goal.description}\n"
        else:
            text += "SECONDARY: Not set\n"

        if self.tertiary_goal:
            text += f"TERTIARY: {self.tertiary_goal.description}\n"
        else:
            text += "TERTIARY: Not set\n"

        if self.completed_goals:
            text += f"\nCOMPLETED GOALS: {len(self.completed_goals)}\n"
            # Show last 3 completed goals
            for goal in self.completed_goals[-3:]:
                text += f"  ✓ {goal.description}\n"

        return text

    def save(self, filepath: str) -> None:
        """Save goals to file.

        Args:
            filepath: Path to save file
        """
        data = {
            'primary': self._goal_to_dict(self.primary_goal),
            'secondary': self._goal_to_dict(self.secondary_goal),
            'tertiary': self._goal_to_dict(self.tertiary_goal),
            'completed': [self._goal_to_dict(g) for g in self.completed_goals],
        }

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        self.logger.debug(f"Saved goals to {filepath}")

    def load(self, filepath: str) -> None:
        """Load goals from file.

        Args:
            filepath: Path to load from
        """
        if not Path(filepath).exists():
            self.logger.warning(f"Goals file not found: {filepath}")
            return

        with open(filepath, 'r') as f:
            data = json.load(f)

        self.primary_goal = self._dict_to_goal(data.get('primary'))
        self.secondary_goal = self._dict_to_goal(data.get('secondary'))
        self.tertiary_goal = self._dict_to_goal(data.get('tertiary'))
        self.completed_goals = [self._dict_to_goal(g) for g in data.get('completed', [])]

        self.logger.info(f"Loaded goals from {filepath}")

    def _goal_to_dict(self, goal: Optional[Goal]) -> Optional[Dict]:
        """Convert goal to dict."""
        if goal is None:
            return None
        return {
            'goal_type': goal.goal_type,
            'description': goal.description,
            'created_at': goal.created_at,
            'completed': goal.completed,
            'completed_at': goal.completed_at,
        }

    def _dict_to_goal(self, data: Optional[Dict]) -> Optional[Goal]:
        """Convert dict to goal."""
        if data is None:
            return None
        return Goal(**data)
