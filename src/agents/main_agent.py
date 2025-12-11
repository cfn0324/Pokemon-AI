"""Main AI agent for Pokemon Red."""

from typing import Dict, Any, Optional, List
from anthropic import Anthropic

from ..utils.logger import get_logger
from ..utils.config import get_config
from ..memory.context_manager import ContextManager
from ..memory.summarizer import Summarizer
from ..tools.goal_manager import GoalManager


class MainAgent:
    """Primary AI agent that makes gameplay decisions."""

    SYSTEM_PROMPT = """You are an AI agent playing Pokemon Red. Your goal is to complete the game by defeating the Elite Four and becoming the Champion.

You have access to the following information:
- Current game state (position, Pokemon party, badges, items, etc.)
- Visual analysis of the screen
- Map exploration status
- Your current goals (primary, secondary, tertiary)
- Recent action history

Available actions:
- Movement: up, down, left, right
- Buttons: a, b, start, select
- wait (to observe state changes)

Guidelines:
1. Work towards your PRIMARY goal, use SECONDARY to enable it, TERTIARY for opportunistic actions
2. Explore systematically - prioritize unexplored areas
3. In battles: Choose effective moves, manage HP/PP, use items wisely
4. Avoid getting stuck - if repeating actions without progress, try a different approach
5. Save progress regularly by entering Pokemon Centers
6. Catch Pokemon to build a strong team
7. Level up Pokemon before major battles
8. Talk to NPCs for information and items

Your response should be in this format:
REASONING: <your analysis of the situation and decision-making process>
ACTION: <single action to take>
GOAL_UPDATE: <any goal updates needed, or "none">

Example response:
REASONING: I'm in Pallet Town and need to reach Professor Oak's lab to get my first Pokemon. The lab is north of my current position.
ACTION: up
GOAL_UPDATE: none
"""

    def __init__(self):
        """Initialize main agent."""
        self.logger = get_logger('MainAgent')
        self.config = get_config()

        # Initialize AI client with custom base_url if provided
        import os
        base_url = os.getenv('ANTHROPIC_BASE_URL')
        if base_url:
            self.client = Anthropic(base_url=base_url)
            self.logger.info(f"Using custom API endpoint: {base_url}")
        else:
            self.client = Anthropic()

        self.model = self.config.get('ai.agents.main.model')
        self.temperature = self.config.get('ai.agents.main.temperature')

        # Sub-components
        self.context = ContextManager(
            max_turns=self.config.get('memory.max_context_turns', 100),
            keep_recent=self.config.get('memory.keep_recent_turns', 20)
        )
        self.summarizer = Summarizer()
        self.goals = GoalManager()

        # Set initial goal
        self.goals.set_primary_goal(
            self.config.get('goals.primary_goal',
                          "Complete Pokemon Red by defeating the Elite Four and Champion")
        )

        self.logger.info("Main agent initialized")

    def decide_action(self, game_state: Dict[str, Any], state_text: str) -> Dict[str, Any]:
        """Decide next action based on game state.

        Args:
            game_state: Game state dict
            state_text: Text representation of state

        Returns:
            Dict with action, reasoning, and goal updates
        """
        turn = game_state['turn']

        # Check if we need summarization
        if self.context.needs_summarization():
            self.logger.info("Triggering context summarization")
            self._summarize_context()

        # Build prompt
        prompt = self._build_prompt(game_state, state_text)

        # Get AI response
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.config.get('ai.max_tokens', 4096),
                temperature=self.temperature,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            # Parse response
            decision = self._parse_response(response_text)

            # Log decision
            self.logger.decision(decision['action'], decision['reasoning'])

            # Add to context
            self.context.add_turn(
                turn_number=turn,
                state=game_state,
                action=decision['action'],
                reasoning=decision['reasoning']
            )

            # Update goals if needed
            if decision.get('goal_update') and decision['goal_update'] != 'none':
                self._process_goal_update(decision['goal_update'])

            return decision

        except Exception as e:
            self.logger.error(f"Failed to get AI decision: {e}")
            # Return safe default action
            return {
                'action': 'wait',
                'reasoning': f'Error occurred: {e}',
                'goal_update': None
            }

    def _build_prompt(self, game_state: Dict[str, Any], state_text: str) -> str:
        """Build prompt for AI.

        Args:
            game_state: Game state dict
            state_text: State text

        Returns:
            Complete prompt
        """
        parts = []

        # Add context (summaries + recent turns)
        context = self.context.get_context_for_ai()
        if context:
            parts.append(context)

        # Add current goals
        parts.append(self.goals.get_goals_text())

        # Add current state
        parts.append(state_text)

        # Add decision request
        parts.append("\nBased on the above information, decide your next action.")

        return "\n\n".join(parts)

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response.

        Args:
            response: AI response text

        Returns:
            Parsed decision dict
        """
        lines = response.strip().split('\n')

        reasoning = ""
        action = "wait"
        goal_update = None

        for line in lines:
            line = line.strip()
            if line.startswith('REASONING:'):
                reasoning = line.replace('REASONING:', '').strip()
            elif line.startswith('ACTION:'):
                action = line.replace('ACTION:', '').strip().lower()
            elif line.startswith('GOAL_UPDATE:'):
                goal_update = line.replace('GOAL_UPDATE:', '').strip()

        return {
            'reasoning': reasoning,
            'action': action,
            'goal_update': goal_update if goal_update != 'none' else None
        }

    def _summarize_context(self) -> None:
        """Summarize context to manage memory."""
        turns_to_summarize = self.context.get_turns_for_summarization()

        if not turns_to_summarize:
            return

        summary = self.summarizer.summarize_turns(turns_to_summarize)

        start_turn = turns_to_summarize[0].turn_number
        end_turn = turns_to_summarize[-1].turn_number

        self.context.add_summary(summary, start_turn, end_turn)

    def _process_goal_update(self, update_text: str) -> None:
        """Process goal update from AI.

        Args:
            update_text: Goal update text
        """
        # Simple parsing of goal updates
        # Format: "PRIMARY: <description>" or "SECONDARY: <description>"
        if update_text.startswith('PRIMARY:'):
            goal = update_text.replace('PRIMARY:', '').strip()
            self.goals.set_primary_goal(goal)
        elif update_text.startswith('SECONDARY:'):
            goal = update_text.replace('SECONDARY:', '').strip()
            self.goals.set_secondary_goal(goal)
        elif update_text.startswith('TERTIARY:'):
            goal = update_text.replace('TERTIARY:', '').strip()
            self.goals.set_tertiary_goal(goal)

    def save_state(self, directory: str) -> None:
        """Save agent state.

        Args:
            directory: Directory to save to
        """
        self.context.save(f"{directory}/context.json")
        self.goals.save(f"{directory}/goals.json")
        self.logger.info(f"Saved agent state to {directory}")

    def load_state(self, directory: str) -> None:
        """Load agent state.

        Args:
            directory: Directory to load from
        """
        self.context.load(f"{directory}/context.json")
        self.goals.load(f"{directory}/goals.json")
        self.logger.info(f"Loaded agent state from {directory}")
