"""Summarizer for compressing game history."""

from typing import List

from ..utils.logger import get_logger
from ..utils.config import get_config
from ..utils.ai_client import AIClient
from .context_manager import Turn


class Summarizer:
    """Creates summaries of game history using AI."""

    def __init__(self):
        """Initialize summarizer."""
        self.logger = get_logger('Summarizer')
        self.config = get_config()
        self.client = AIClient(logger=self.logger)

        self.logger.info("Summarizer initialized")

    def summarize_turns(self, turns: List[Turn]) -> str:
        """Summarize a list of turns.

        Args:
            turns: List of turns to summarize

        Returns:
            Summary text
        """
        if not turns:
            return "No activity to summarize."

        self.logger.info(f"Summarizing {len(turns)} turns")

        # Prepare turn data for summarization
        turn_descriptions = []
        for turn in turns:
            desc = f"Turn {turn.turn_number}: "
            if turn.action:
                desc += f"Action={turn.action}"
            if turn.result:
                desc += f", Result={turn.result}"
            turn_descriptions.append(desc)

        prompt = f"""You are summarizing a sequence of gameplay actions from Pokemon Red.

Please create a concise summary (2-3 sentences) of the following {len(turns)} turns, focusing on:
- Major progress made (badges earned, Pokemon caught, significant locations reached)
- Current objectives being pursued
- Any challenges or obstacles encountered

Turns to summarize:
{chr(10).join(turn_descriptions)}

Provide ONLY the summary, no additional commentary."""

        try:
            response = self.client.create_message(
                model=self.config.get('ai.model'),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3,
            )

            summary = response.content[0].text.strip()
            self.logger.info(f"Generated summary: {summary[:100]}...")

            return summary

        except Exception as e:
            self.logger.error(f"Failed to generate summary: {e}")
            return f"Summary generation failed. {len(turns)} turns of activity occurred."

    def summarize_text(self, text: str, max_length: int = 200) -> str:
        """Summarize arbitrary text.

        Args:
            text: Text to summarize
            max_length: Maximum tokens for summary

        Returns:
            Summary
        """
        prompt = f"""Summarize the following text concisely:

{text}

Provide only the summary."""

        try:
            response = self.client.create_message(
                model=self.config.get('ai.model'),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_length,
                temperature=0.3,
            )

            return response.content[0].text.strip()

        except Exception as e:
            self.logger.error(f"Failed to summarize text: {e}")
            return text[:max_length] + "..."
