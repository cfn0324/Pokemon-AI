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
    screen_type: Optional[str]
    reasoning: Optional[str]
    result: Optional[str]
    decision_source: Optional[str] = None
    decision_path: Optional[str] = None
    model_latency_seconds: Optional[float] = None
    model_request_count: Optional[int] = None


@dataclass
class ContextNote:
    """External guidance note kept in context for a limited time."""
    timestamp: str
    source: str
    text: str


@dataclass
class TaskNotebook:
    """Compact working-memory note for the next few decisions."""
    updated_at: str
    focus: str = ""
    next_step: str = ""
    recent_progress: str = ""
    avoid: str = ""


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
        self.notes: List[ContextNote] = []
        self.task_notebook: Optional[TaskNotebook] = None

        # Current summary period
        self.current_period_start = 0

        self.logger.info(f"Context manager initialized (max_turns={max_turns}, keep_recent={keep_recent})")

    def add_turn(self, turn_number: int, state: Dict[str, Any],
                 action: Optional[str] = None, screen_type: Optional[str] = None,
                 reasoning: Optional[str] = None,
                 result: Optional[str] = None,
                 decision_source: Optional[str] = None,
                 decision_path: Optional[str] = None,
                 model_latency_seconds: Optional[float] = None,
                 model_request_count: Optional[int] = None) -> None:
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
            screen_type=screen_type,
            reasoning=reasoning,
            result=result,
            decision_source=decision_source,
            decision_path=decision_path,
            model_latency_seconds=model_latency_seconds,
            model_request_count=model_request_count,
        )

        self.recent_turns.append(turn)

        # Check if we need to summarize
        if len(self.recent_turns) >= self.max_turns:
            self.logger.info(f"Reached {self.max_turns} turns, triggering summarization")
            # We'll trigger summarization in the agent
            # For now, just keep recent turns
            self._trim_to_recent()

    def update_last_turn_result(self, result: str) -> None:
        """Attach the latest observed outcome to the most recent turn."""
        if not self.recent_turns:
            return

        cleaned = " ".join((result or "").split()).strip()
        if not cleaned:
            return
        self.recent_turns[-1].result = cleaned

    def add_note(self, text: str, source: str = "system", max_notes: int = 6) -> None:
        """Add a short guidance note that should stay in prompt context."""
        cleaned = " ".join((text or "").split()).strip()
        if not cleaned:
            return

        self.notes.append(
            ContextNote(
                timestamp=datetime.now().isoformat(),
                source=source,
                text=cleaned,
            )
        )
        if len(self.notes) > max_notes:
            self.notes = self.notes[-max_notes:]

    def remove_notes_matching(self, query: str) -> int:
        """Remove notes whose text contains the query."""
        needle = " ".join((query or "").split()).strip().lower()
        if not needle:
            return 0

        kept: List[ContextNote] = []
        removed = 0
        for note in self.notes:
            if needle in note.text.lower():
                removed += 1
                continue
            kept.append(note)

        if removed:
            self.notes = kept
        return removed

    def set_task_notebook(
        self,
        *,
        focus: str = "",
        next_step: str = "",
        recent_progress: str = "",
        avoid: str = "",
    ) -> None:
        """Update the compact working-memory note for the prompt."""
        notebook = TaskNotebook(
            updated_at=datetime.now().isoformat(),
            focus=" ".join((focus or "").split()).strip(),
            next_step=" ".join((next_step or "").split()).strip(),
            recent_progress=" ".join((recent_progress or "").split()).strip(),
            avoid=" ".join((avoid or "").split()).strip(),
        )
        if not any((notebook.focus, notebook.next_step, notebook.recent_progress, notebook.avoid)):
            self.task_notebook = None
            return
        self.task_notebook = notebook

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

        if self.task_notebook:
            context_parts.append("=== TASK NOTE ===\n")
            if self.task_notebook.focus:
                context_parts.append(f"FOCUS_NOW: {self.task_notebook.focus}\n")
            if self.task_notebook.next_step:
                context_parts.append(f"NEXT_STEP: {self.task_notebook.next_step}\n")
            if self.task_notebook.recent_progress:
                context_parts.append(f"RECENT_PROGRESS: {self.task_notebook.recent_progress}\n")
            if self.task_notebook.avoid:
                context_parts.append(f"AVOID_REPEAT: {self.task_notebook.avoid}\n")
            context_parts.append("\n")

        # Add summaries
        if self.summaries:
            context_parts.append("=== PREVIOUS ACTIVITY SUMMARY ===\n")
            for summary in self.summaries:
                context_parts.append(summary + "\n")
            context_parts.append("\n")

        # Add recent turns
        if self.recent_turns:
            turns_for_prompt = self.recent_turns[-max(1, self.keep_recent):]
            reasoning_cutoff = max(0, len(turns_for_prompt) - 4)
            context_parts.append("=== RECENT TURNS ===\n")
            for index, turn in enumerate(turns_for_prompt):
                turn_text = f"\nTurn {turn.turn_number}:\n"
                if turn.action:
                    turn_text += f"Action: {turn.action}\n"
                if turn.screen_type:
                    turn_text += f"Screen Type: {turn.screen_type}\n"
                if turn.reasoning and index >= reasoning_cutoff:
                    turn_text += f"Reasoning: {turn.reasoning}\n"
                if turn.result:
                    turn_text += f"Result: {turn.result}\n"
                context_parts.append(turn_text)

        if self.notes:
            context_parts.append("\n=== GUIDANCE NOTES ===\n")
            for note in self.notes[-4:]:
                context_parts.append(f"- [{note.source}] {note.text}\n")

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
            'task_notebook': (
                {
                    'updated_at': self.task_notebook.updated_at,
                    'focus': self.task_notebook.focus,
                    'next_step': self.task_notebook.next_step,
                    'recent_progress': self.task_notebook.recent_progress,
                    'avoid': self.task_notebook.avoid,
                }
                if self.task_notebook
                else None
            ),
            'notes': [
                {
                    'timestamp': note.timestamp,
                    'source': note.source,
                    'text': note.text,
                }
                for note in self.notes
            ],
            'recent_turns': [
                {
                    'turn_number': t.turn_number,
                    'timestamp': t.timestamp,
                    'action': t.action,
                    'screen_type': t.screen_type,
                    'reasoning': t.reasoning,
                    'result': t.result,
                    'decision_source': t.decision_source,
                    'decision_path': t.decision_path,
                    'model_latency_seconds': t.model_latency_seconds,
                    'model_request_count': t.model_request_count,
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

        self.recent_turns = []
        self.summaries = data.get('summaries', [])
        notebook_data = data.get('task_notebook') or None
        self.task_notebook = (
            TaskNotebook(
                updated_at=notebook_data.get('updated_at', datetime.now().isoformat()),
                focus=notebook_data.get('focus', ''),
                next_step=notebook_data.get('next_step', ''),
                recent_progress=notebook_data.get('recent_progress', ''),
                avoid=notebook_data.get('avoid', ''),
            )
            if notebook_data
            else None
        )
        self.notes = [
            ContextNote(
                timestamp=note.get('timestamp', datetime.now().isoformat()),
                source=note.get('source', 'system'),
                text=note.get('text', ''),
            )
            for note in data.get('notes', [])
            if note.get('text')
        ]
        self.current_period_start = data.get('current_period_start', 0)

        # Reconstruct recent turns (without full state data)
        for turn_data in data.get('recent_turns', []):
            turn = Turn(
                turn_number=turn_data['turn_number'],
                timestamp=turn_data['timestamp'],
                state={},  # State not saved to reduce size
                action=turn_data.get('action'),
                screen_type=turn_data.get('screen_type'),
                reasoning=turn_data.get('reasoning'),
                result=turn_data.get('result'),
                decision_source=turn_data.get('decision_source'),
                decision_path=turn_data.get('decision_path'),
                model_latency_seconds=turn_data.get('model_latency_seconds'),
                model_request_count=turn_data.get('model_request_count'),
            )
            self.recent_turns.append(turn)

        self.logger.info(f"Loaded context from {filepath} ({len(self.summaries)} summaries, {len(self.recent_turns)} recent turns)")

    def clear(self) -> None:
        """Clear all context."""
        self.recent_turns.clear()
        self.summaries.clear()
        self.task_notebook = None
        self.notes.clear()
        self.current_period_start = 0
        self.logger.info("Cleared all context")
