"""Context manager for long-term memory management."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

from ..utils.logger import get_logger


@dataclass
class Turn:
    """Represents a single turn in the game."""
    turn_number: int
    timestamp: str
    state: Dict[str, Any]
    action: Optional[str]
    reasoning: Optional[str]
    result: Optional[str]


class ContextManager:
    """Manages AI context with periodic summarization."""

    def __init__(self, max_turns: int = 100, keep_recent: int = 20):
        """Initialize context manager.

        Args:
            max_turns: Summarize context after this many turns
            keep_recent: Keep this many recent turns in full detail
        """
        self.logger = get_logger('ContextManager')
        self.max_turns = max_turns
        self.keep_recent = keep_recent

        # Full turn history (recent only)
        self.recent_turns: List[Turn] = []

        # Summarized history
        self.summaries: List[str] = []

        # Current summary period
        self.current_period_start = 0

        self.logger.info(f"Context manager initialized (max_turns={max_turns}, keep_recent={keep_recent})")

    def add_turn(self, turn_number: int, state: Dict[str, Any],
                 action: Optional[str] = None, reasoning: Optional[str] = None,
                 result: Optional[str] = None) -> None:
        """Add a new turn to context.

        Args:
            turn_number: Turn number
            state: Game state
            action: Action taken
            reasoning: AI reasoning
            result: Result of action
        """
        turn = Turn(
            turn_number=turn_number,
            timestamp=datetime.now().isoformat(),
            state=state,
            action=action,
            reasoning=reasoning,
            result=result
        )

        self.recent_turns.append(turn)

        # Check if we need to summarize
        if len(self.recent_turns) >= self.max_turns:
            self.logger.info(f"Reached {self.max_turns} turns, triggering summarization")
            # We'll trigger summarization in the agent
            # For now, just keep recent turns
            self._trim_to_recent()

    def _trim_to_recent(self) -> None:
        """Keep only recent turns, discarding old ones."""
        if len(self.recent_turns) > self.keep_recent:
            old_turns = self.recent_turns[:-self.keep_recent]
            self.recent_turns = self.recent_turns[-self.keep_recent:]
            self.logger.debug(f"Trimmed to {len(self.recent_turns)} recent turns, discarded {len(old_turns)}")

    def add_summary(self, summary: str, period_start: int, period_end: int) -> None:
        """Add a summary of a period.

        Args:
            summary: Summary text
            period_start: Starting turn of period
            period_end: Ending turn of period
        """
        summary_entry = f"[Turns {period_start}-{period_end}]: {summary}"
        self.summaries.append(summary_entry)
        self.current_period_start = period_end + 1
        self.logger.info(f"Added summary for turns {period_start}-{period_end}")

    def get_context_for_ai(self) -> str:
        """Get formatted context for AI consumption.

        Returns:
            Formatted context string
        """
        context_parts = []

        # Add summaries
        if self.summaries:
            context_parts.append("=== PREVIOUS ACTIVITY SUMMARY ===\n")
            for summary in self.summaries:
                context_parts.append(summary + "\n")
            context_parts.append("\n")

        # Add recent turns
        if self.recent_turns:
            context_parts.append("=== RECENT TURNS (Detailed) ===\n")
            for turn in self.recent_turns:
                turn_text = f"\n--- Turn {turn.turn_number} ---\n"
                if turn.action:
                    turn_text += f"Action: {turn.action}\n"
                if turn.reasoning:
                    turn_text += f"Reasoning: {turn.reasoning}\n"
                if turn.result:
                    turn_text += f"Result: {turn.result}\n"
                context_parts.append(turn_text)

        return "".join(context_parts)

    def needs_summarization(self) -> bool:
        """Check if context needs summarization.

        Returns:
            True if summarization needed
        """
        return len(self.recent_turns) >= self.max_turns

    def get_turns_for_summarization(self) -> List[Turn]:
        """Get turns that need to be summarized.

        Returns:
            List of turns to summarize
        """
        # Return all but the most recent turns
        if len(self.recent_turns) > self.keep_recent:
            return self.recent_turns[:-self.keep_recent]
        return []

    def save(self, filepath: str) -> None:
        """Save context to file.

        Args:
            filepath: Path to save file
        """
        data = {
            'summaries': self.summaries,
            'recent_turns': [
                {
                    'turn_number': t.turn_number,
                    'timestamp': t.timestamp,
                    'action': t.action,
                    'reasoning': t.reasoning,
                    'result': t.result,
                }
                for t in self.recent_turns
            ],
            'current_period_start': self.current_period_start,
        }

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        self.logger.info(f"Saved context to {filepath}")

    def load(self, filepath: str) -> None:
        """Load context from file.

        Args:
            filepath: Path to load from
        """
        if not Path(filepath).exists():
            self.logger.warning(f"Context file not found: {filepath}")
            return

        with open(filepath, 'r') as f:
            data = json.load(f)

        self.summaries = data.get('summaries', [])
        self.current_period_start = data.get('current_period_start', 0)

        # Reconstruct recent turns (without full state data)
        for turn_data in data.get('recent_turns', []):
            turn = Turn(
                turn_number=turn_data['turn_number'],
                timestamp=turn_data['timestamp'],
                state={},  # State not saved to reduce size
                action=turn_data.get('action'),
                reasoning=turn_data.get('reasoning'),
                result=turn_data.get('result'),
            )
            self.recent_turns.append(turn)

        self.logger.info(f"Loaded context from {filepath} ({len(self.summaries)} summaries, {len(self.recent_turns)} recent turns)")

    def clear(self) -> None:
        """Clear all context."""
        self.recent_turns.clear()
        self.summaries.clear()
        self.current_period_start = 0
        self.logger.info("Cleared all context")
