"""Critic agent for evaluating strategy and decisions."""

from typing import Dict, Any, List
from anthropic import Anthropic

from ..utils.logger import get_logger
from ..utils.config import get_config


class CriticAgent:
    """Specialized agent for critiquing strategy and identifying issues."""

    SYSTEM_PROMPT = """You are a strategy critic for Pokemon Red gameplay. Your role is to:

1. Analyze recent actions and outcomes
2. Identify poor strategies or stuck states
3. Suggest alternative approaches
4. Point out missed opportunities

You are NOT playing the game - you're evaluating the main agent's performance.

Be constructive and specific in your criticism.

Response format:
ASSESSMENT: <overall assessment of recent performance>
ISSUES: <specific problems identified>
SUGGESTIONS: <concrete suggestions for improvement>
"""

    def __init__(self):
        """Initialize critic agent."""
        self.logger = get_logger('Critic')
        self.config = get_config()

        # Initialize AI client with custom base_url if provided
        import os
        base_url = os.getenv('ANTHROPIC_BASE_URL')
        if base_url:
            self.client = Anthropic(base_url=base_url)
        else:
            self.client = Anthropic()

        self.model = self.config.get('ai.agents.critic.model')
        self.temperature = self.config.get('ai.agents.critic.temperature')

        self.logger.info("Critic agent initialized")

    def critique(self, recent_history: str, current_state: Dict[str, Any]) -> Dict[str, str]:
        """Provide critique of recent performance.

        Args:
            recent_history: Recent action history
            current_state: Current game state

        Returns:
            Dict with assessment, issues, suggestions
        """
        self.logger.info("Generating strategy critique")

        prompt = f"""Evaluate the following recent gameplay:

{recent_history}

Current state:
- Badges: {current_state.get('memory', {}).get('badge_count', 0)}/8
- Party size: {len(current_state.get('memory', {}).get('party', []))}
- Turn: {current_state.get('turn', 0)}

Provide your critique."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                temperature=self.temperature,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            critique = self._parse_critique(response_text)

            self.logger.info("Critique generated")

            return critique

        except Exception as e:
            self.logger.error(f"Critique failed: {e}")
            return {
                'assessment': 'Unable to generate critique',
                'issues': str(e),
                'suggestions': 'Continue with current strategy'
            }

    def _parse_critique(self, response: str) -> Dict[str, str]:
        """Parse critique from response.

        Args:
            response: AI response

        Returns:
            Critique dict
        """
        critique = {
            'assessment': '',
            'issues': '',
            'suggestions': ''
        }

        current_section = None

        for line in response.split('\n'):
            line = line.strip()

            if line.startswith('ASSESSMENT:'):
                current_section = 'assessment'
                critique['assessment'] = line.replace('ASSESSMENT:', '').strip()
            elif line.startswith('ISSUES:'):
                current_section = 'issues'
                critique['issues'] = line.replace('ISSUES:', '').strip()
            elif line.startswith('SUGGESTIONS:'):
                current_section = 'suggestions'
                critique['suggestions'] = line.replace('SUGGESTIONS:', '').strip()
            elif current_section and line:
                critique[current_section] += ' ' + line

        return critique
