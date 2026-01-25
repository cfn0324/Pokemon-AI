"""Main AI agent for Pokemon Red."""

import base64
import re
from typing import Dict, Any, Optional, List
from anthropic import Anthropic

from ..utils.logger import get_logger
from ..utils.config import get_config
from ..memory.context_manager import ContextManager
from ..memory.summarizer import Summarizer
from ..tools.goal_manager import GoalManager


class MainAgent:
    """Primary AI agent that makes gameplay decisions."""

    VALID_ACTIONS = {
        "up",
        "down",
        "left",
        "right",
        "a",
        "b",
        "start",
        "select",
        "wait",
    }

    _FIELD_RE = re.compile(
        r"^\s*(reasoning|action|goal_update)\s*[:：]\s*(.*)\s*$",
        flags=re.IGNORECASE,
    )

    SYSTEM_PROMPT = """You are an AI agent playing Pokemon Red. Your goal is to complete the game by defeating the Elite Four and becoming the Champion.

You have access to the following information each turn:
- Memory-based game state (position/map_id, Pokemon party, badges, money, in-battle flag)
- Current screenshot image (pixel vision) to read menus, battles, dialogue boxes, NPCs, player position, and obstacles
- Map exploration status
- Your current goals (primary, secondary, tertiary)
- Recent action history

Important constraints:
- Use the screenshot to confirm UI state (battle/menu/dialog/overworld). If pixels conflict with memory flags, trust the screenshot for UI state, and memory for stats.
- Avoid getting stuck: if position/in_battle/money/menu flags do not change for several turns, change strategy (different direction, wait, exit menus with B).

Available actions:
- Movement: up, down, left, right
- Buttons: a, b, start, select
- wait (to observe state changes)

Guidelines:
1. Work towards your PRIMARY goal, use SECONDARY to enable it, TERTIARY for opportunistic actions
2. Explore systematically - prioritize unexplored areas
3. In battles: Choose effective moves, manage HP/PP, use items wisely
4. Save progress regularly by entering Pokemon Centers
5. Catch Pokemon to build a strong team; level up before major battles
6. Talk to NPCs for information and items
7. If in a menu/dialog, use B to exit unless you intentionally need to navigate it.

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
        api_key = os.getenv('OPENAI_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
        base_url = os.getenv('OPENAI_BASE_URL') or os.getenv('ANTHROPIC_BASE_URL')
        client_kwargs = {}
        if api_key:
            client_kwargs['api_key'] = api_key
        if base_url:
            client_kwargs['base_url'] = base_url
            self.logger.info(f"Using custom API endpoint: {base_url}")

        self.client = Anthropic(**client_kwargs)

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

    def decide_action(
        self,
        game_state: Dict[str, Any],
        state_text: str,
        screenshot_bytes: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """Decide next action based on game state.

        Args:
            game_state: Game state dict
            state_text: Text representation of state
            screenshot_bytes: Optional PNG bytes of the current screen

        Returns:
            Dict with action, reasoning, and goal updates
        """
        turn = game_state['turn']

        # Check if we need summarization
        if self.context.needs_summarization():
            self.logger.info("Triggering context summarization")
            self._summarize_context()

        # Build prompt
        prompt = self._build_prompt(game_state, state_text, has_screenshot=bool(screenshot_bytes))

        # Get AI response
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.config.get('ai.max_tokens', 4096),
                temperature=self.temperature,
                system=self.SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": self._build_content(prompt, screenshot_bytes)
                }]
            )

            response_text = response.content[0].text
            self.logger.debug(f"Raw model response (truncated): {response_text[:800]!r}")

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

    def _build_prompt(
        self,
        game_state: Dict[str, Any],
        state_text: str,
        has_screenshot: bool
    ) -> str:
        """Build prompt for AI.

        Args:
            game_state: Game state dict
            state_text: State text
            has_screenshot: Whether a screenshot is attached

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

        # Indicate screenshot availability
        if has_screenshot:
            parts.append("A current game screenshot (PNG) is attached. Use pixel details to identify menus, battles, dialogue boxes, obstacles, NPCs, and the player's position.")
        else:
            parts.append("No screenshot is attached this turn; rely on memory fields only.")

        # Add decision request
        parts.append("\nBased on the above information, decide your next action.")

        return "\n\n".join(parts)

    def _build_content(self, prompt: str, screenshot_bytes: Optional[bytes]) -> List[Dict[str, Any]]:
        """Build multimodal content payload."""
        content: List[Dict[str, Any]] = []

        if screenshot_bytes:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(screenshot_bytes).decode("utf-8")
                }
            })

        content.append({"type": "text", "text": prompt})
        return content

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response.

        Args:
            response: AI response text

        Returns:
            Parsed decision dict
        """
        response = (response or "").strip()
        if not response:
            return {"reasoning": "", "action": "wait", "goal_update": None}

        lines = response.splitlines()

        reasoning: str = ""
        action_raw: Optional[str] = None
        goal_update: Optional[str] = None

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            match = self._FIELD_RE.match(line)
            if not match:
                i += 1
                continue

            field = match.group(1).lower()
            value = (match.group(2) or "").strip()

            if field == "reasoning":
                if value:
                    reasoning = value
                else:
                    reasoning, i = self._collect_multiline_field(lines, i + 1)
                    continue

            if field == "action":
                if value:
                    action_raw = value
                else:
                    action_raw = self._collect_next_value_line(lines, i + 1)

            if field == "goal_update":
                if value:
                    goal_update = value
                else:
                    goal_update = self._collect_next_value_line(lines, i + 1)

            i += 1

        action = self._normalize_action(action_raw)
        if not action:
            action = self._infer_action_from_text(response)
        if action not in self.VALID_ACTIONS:
            action = "wait"

        if goal_update:
            goal_update = goal_update.strip()
            if goal_update.lower() == "none":
                goal_update = None

        if not reasoning:
            reasoning = response
        reasoning = self._compact_text(reasoning, max_chars=400)

        return {
            "reasoning": reasoning,
            "action": action,
            "goal_update": goal_update,
        }

    def _collect_multiline_field(self, lines: List[str], start_index: int) -> tuple[str, int]:
        """Collect a multi-line field value until the next labeled field."""
        collected: List[str] = []
        i = start_index
        while i < len(lines):
            raw = lines[i].strip()
            if self._FIELD_RE.match(raw):
                break
            if raw:
                collected.append(raw)
            i += 1
        return " ".join(collected).strip(), i

    def _collect_next_value_line(self, lines: List[str], start_index: int) -> Optional[str]:
        """Get the next non-empty line that isn't another field label."""
        i = start_index
        while i < len(lines):
            raw = lines[i].strip()
            if not raw:
                i += 1
                continue
            if self._FIELD_RE.match(raw):
                return None
            return raw
        return None

    def _normalize_action(self, action: Optional[str]) -> Optional[str]:
        """Normalize a raw action string to a valid action token."""
        if not action:
            return None

        cleaned = action.strip().strip("`\"'").lower()

        # Handle formats like "press start", "ACTION: start", "start (or a)".
        for token in re.split(r"[\s,;()]+", cleaned):
            if token in self.VALID_ACTIONS:
                return token

        match = re.search(r"\b(up|down|left|right|start|select|wait)\b", cleaned)
        if match:
            return match.group(1).lower()

        # Avoid false positives for single-letter actions.
        if cleaned in {"a", "b"}:
            return cleaned

        return None

    def _infer_action_from_text(self, response: str) -> Optional[str]:
        """Heuristic fallback when the model doesn't output the required ACTION: line."""
        candidates: List[tuple[int, str]] = []

        def add(pattern: str, action: str, flags: int = 0) -> None:
            match = re.search(pattern, response, flags)
            if match:
                candidates.append((match.start(), action))

        # Prefer explicit button mentions.
        add(r"`\s*start\s*`", "start", re.IGNORECASE)
        add(r"\bpress\s+(?:the\s+)?start\b", "start", re.IGNORECASE)
        add(r"\bSTART\b", "start")
        add(r"按(?:下|住|一下)?\s*start", "start", re.IGNORECASE)

        add(r"`\s*select\s*`", "select", re.IGNORECASE)
        add(r"\bpress\s+(?:the\s+)?select\b", "select", re.IGNORECASE)
        add(r"\bSELECT\b", "select")
        add(r"按(?:下|住|一下)?\s*select", "select", re.IGNORECASE)

        add(r"`\s*a\s*`", "a", re.IGNORECASE)
        add(r"\bpress\s+(?:the\s+)?a\b", "a", re.IGNORECASE)
        add(r"按(?:下|住|一下)?\s*a(?:键)?", "a", re.IGNORECASE)

        add(r"`\s*b\s*`", "b", re.IGNORECASE)
        add(r"\bpress\s+(?:the\s+)?b\b", "b", re.IGNORECASE)
        add(r"按(?:下|住|一下)?\s*b(?:键)?", "b", re.IGNORECASE)

        # Movement and wait.
        for move in ["up", "down", "left", "right", "wait"]:
            add(rf"`\s*{move}\s*`", move, re.IGNORECASE)
            add(rf"\b(move|go|walk)\s+{move}\b", move, re.IGNORECASE)

        add(r"(向|往)上|上移", "up")
        add(r"(向|往)下|下移", "down")
        add(r"(向|往)左|左移", "left")
        add(r"(向|往)右|右移", "right")
        add(r"等待|先等|观望", "wait")

        if candidates:
            candidates.sort(key=lambda t: t[0])
            return candidates[0][1]

        # Handle terse responses like "a（确认继续）" or "b" on their own.
        terse = re.search(
            r"(?mi)^\s*(?:action\s*[:：]\s*)?([ab])\s*(?:$|[\s\(\（\)\）:：,，.。!！?？])",
            response,
        )
        if terse:
            return terse.group(1).lower()

        # Last-ditch: pick the first mention of a movement or wait token.
        match = re.search(r"\b(up|down|left|right|wait)\b", response, re.IGNORECASE)
        if match:
            return match.group(1).lower()

        return None

    def _compact_text(self, text: str, max_chars: int = 400) -> str:
        """Compact text for logging/context to keep tokens low."""
        compact = " ".join((text or "").split()).strip()
        if len(compact) > max_chars:
            return compact[: max_chars - 3].rstrip() + "..."
        return compact

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
