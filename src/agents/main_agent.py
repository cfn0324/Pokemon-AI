"""Main AI agent for Pokemon Red."""

import base64
import re
import time
from typing import Dict, Any, Optional, List

from ..utils.logger import get_logger
from ..utils.config import get_config
from ..utils.ai_client import AIClient
from ..memory.context_manager import ContextManager
from ..memory.summarizer import Summarizer
from ..tools.goal_manager import GoalManager


class AIDecisionRetrySignal(RuntimeError):
    """Signal that the current observation should be retried without spending a turn."""

    def __init__(self, message: str, *, source: str, retry_after_seconds: float = 0.0):
        super().__init__(message)
        self.source = source
        self.retry_after_seconds = max(0.0, float(retry_after_seconds or 0.0))


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

    VALID_SCREEN_TYPES = {
        "startup",
        "title",
        "startup_menu",
        "options_menu",
        "dialogue",
        "cutscene",
        "text_entry",
        "naming_screen",
        "battle",
        "menu",
        "overworld",
        "indoor",
        "unknown",
    }

    _FIELD_RE = re.compile(
        r"^\s*(reasoning|action|goal_update)\s*[:：]\s*(.*)\s*$",
        flags=re.IGNORECASE,
    )

    SYSTEM_PROMPT = """You are an AI agent playing Pokemon Red.

The Champion objective is only the long-term mission. Do NOT try to solve the whole game at once.
Each turn, obey this priority order:
1. CURRENT FOCUS
2. The first unfinished LIVE TODO item
3. PRIMARY goal
4. SECONDARY goal
5. TERTIARY goal

Think in very small steps. Your action should advance the next 1-20 in-game actions, not the whole run.
Act like a careful first-time player of Pokemon Red, not a speedrunner and not a remake player.
Do not assume remake-only items or events (for example TEA from FireRed/LeafGreen) unless the current evidence explicitly supports them.
If prior knowledge, old summaries, or current goals conflict with the current RAM/screen evidence, trust the current evidence and correct the plan.
If recent action results say repeated A presses caused no visible state change, stop assuming dialogue is still progressing and switch tactic.

You have access to the following information each turn:
- Memory-based game state (position/map_id, Pokemon party, badges, money, in-battle flag)
- Current raw screenshot image to read menus, battles, dialogue boxes, NPCs, player position, and obstacles
- Map exploration status
- A navigation advisor derived from map memory, visit counts, known blocked directions, known warps, reachable frontier tiles, and frontier novelty scoring
- A recent-movement summary that warns when you have been revisiting a tiny local area
- A structured battle summary that distinguishes new encounters, ongoing battles, and post-battle dialogue
- A live plan with long-term mission, current stage, current focus, and a real-time todo list
- Recent action history

Important constraints:
- The harness does not run a local pixel-classifier for you. If the state text says local vision is disabled, that only means no extra CV hints were generated; you still have the screenshot itself.
- Use the screenshot to confirm UI state (battle/menu/dialogue/overworld). If pixels conflict with memory flags, trust the screenshot for UI state and memory for stats.
- If RAM says a text box is active but the screenshot does not show a real bordered dialogue panel with readable text or a prompt arrow, suspect a stale UI flag and trust the room/map screenshot instead.
- If the screenshot is still Oak's intro, a naming screen, a title/menu, or another scripted scene, report that SCREEN_TYPE directly even if RAM already shows room coordinates.
- In boot/title/new-game flow, use the visible UI on the screenshot. Do not switch from START to movement or random buttons unless the screen visibly changes.
- The screenshot is a moving camera viewport, not a full-room map. Do not treat the current frame as a complete fixed layout of the whole room.
- In overworld movement, the camera usually follows the player. The player being near the lower part of the screen does NOT imply there is more walkable room below.
- Off-screen or unrendered space is unknown. Black screen-edge space is not evidence of walkable floor.
- Avoid getting stuck. If movement is not producing progress, change tactic: try another direction, leave menus with B, or face a blocker/NPC and press A.
- Before the first Pokemon is obtained, your only job is early-story progression: leave the room, leave the house, follow the mandatory opening route, talk to blockers, and get the starter.
- Before the first Pokemon is obtained, optional flavor interactions are low priority. Ignore bedroom/house PC, TV, bookshelf, and other furniture unless the screenshot shows active dialogue there or nothing else can advance progress.
- If control has returned in the bedroom or house, prefer stairs, doors, and route exits over furniture inspection.
- Merely facing an object does not make it the correct target. If movement is available and no text box is open, step toward the exit instead of pressing A on optional furniture.
- When a person, dialogue trigger, or obstacle is clearly blocking progress, treat it as the current task.
- Do not wander because of the long-term mission. Near-term progression is always more important than distant plans.
- On player-name or rival-name screens, minimize wasted turns. Prefer a short simple name or a visible preset choice if that ends the naming step faster.
- On naming screens, do not press A repeatedly on the same letter unless you intentionally want repeated letters. If one character was just entered, move before pressing A again unless repetition is desired.
- When a name field is already full, press START to confirm it instead of adding more letters.
- Use the navigation advisor as reliable memory: known exits, blocked directions, warp points, frontier routes, and visit counts come from actual observed play.
- If the state text includes frontier novelty or revisit-pressure metrics, use them to avoid repeatedly probing a locally exhausted frontier when better alternatives exist.
- If the state text includes a battle summary, trust it for battle phase: for example, post-battle dialogue means you should finish the text instead of trying to walk away.
- If the exit, stairs, or door is not visible yet, your job is to explore until it becomes visible. Exploration is progress.
- If the state text reports a loop warning or says recent movement stayed inside a tiny box, treat the current local frontier as suspicious and deliberately change route instead of probing the same edge again.
- For movement decisions, first do a local visual check of the four directions around the player.
- Treat large pure-black regions, screenshot crop/void, walls, furniture, and solid obstacles as non-walkable.
- A direction is bad if the floor does not visibly continue there, or if it quickly runs into black void or a solid object.
- Prefer directions where visible floor continues for more than one tile. If bottom and right are mostly black while upper floor continues, move up.
- In Pokemon Red indoor rooms, walkable ground is usually visible patterned floor tiles. Pure black areas are usually off-room void, hidden screen area, or non-walkable space, not unexplored floor.
- Never assume a staircase, door, or exit exists inside a black area. If the exit is not rendered on-screen yet, move only across clearly visible floor to search for it.
- Only call a direction explorable if there is continuous visible floor from the player's tile into that direction.
- If a direction is mostly black within 1-2 tiles, reject it even if you hope the room extends there.
- When choosing between a visible-floor direction and a black/uncertain direction, always choose the visible-floor direction.
- Do not infer room extension from sprite placement alone. Decide from visible floor continuity, not from "the player is near the bottom so the room probably continues downward."

Available actions:
- Movement: up, down, left, right
- Buttons: a, b, start, select
- wait (to observe state changes)

Guidelines:
1. Prefer the smallest concrete step that advances the current focus.
2. In small interiors, prioritize finding the exit before broad exploration.
3. In battles, finish the current battle safely before returning to movement goals.
4. Talk to NPCs when they block the route or likely trigger story progress.
5. If in a menu or dialogue unintentionally, use B to exit unless A is clearly needed to advance.
6. Update the todo list when you discover a blocker, complete a step, or need to re-focus.
7. If you cannot see the exit yet, explore unseen tiles systematically. Use map exploration info and prefer directions that lead to unvisited coordinates.
8. Do not press the same blocked direction repeatedly. After 1-2 failed moves, rotate and search a different edge of the room.
9. In a room, a good default search pattern is: check one side, then sweep along the wall/perimeter until you uncover the exit or stairs.
10. Before choosing a movement action, explicitly compare up/down/left/right in the screenshot and reject directions that look clipped, black, or obstructed.
11. Do not confuse screenshot darkness with traversable space. Black does not mean open.
12. If your previous reasoning says a black region is probably an exit path, that is usually a mistake; re-check the visible floor instead.
13. In the bedroom opening specifically, if the lower half of the screen is black and only the upper room floor is visible, search across the visible room floor rather than moving into the black area.
14. If the visible patterned floor continues upward but fades into black downward, upward is the better exploration direction even if the player sprite is currently low on the screen.
15. Before choosing a direction, ask: "Do I see actual floor tiles continuing there?" If not, do not move that way.
16. Only issue GOAL_UPDATE commands when current evidence strongly supports the update. Do not rewrite goals from speculation.
17. If a recent result says your last move failed or produced no movement, do not repeat the same blocked movement unless new evidence appears.
18. If a recent result says repeated A caused no visible state change and the screenshot still looks like a room, reclassify the screen as indoor/overworld instead of dialogue and try movement or B.

Classify the current screenshot into exactly one of these SCREEN_TYPE values:
- startup
- title
- startup_menu
- options_menu
- dialogue
- cutscene
- text_entry
- naming_screen
- battle
- menu
- overworld
- indoor
- unknown

Your response must be exactly in this format:
SCREEN_TYPE: <single screen type from the allowed list>
REASONING: <brief analysis tied to the current focus or top todo; for movement, mention which directions look blocked vs open>
ACTION: <single action to take>
GOAL_UPDATE: <"none" or one or more lines using these commands:
FOCUS: ...
ADD_TODO: ...
NEXT_TODO: ...
DONE_TODO: ...
REMOVE_TODO: ...
PRIMARY: ...
SECONDARY: ...
TERTIARY: ...
BLOCKED: ...>

Output rules:
- Plain text only. No markdown bullets, no code fences, no preamble, no trailing note.
- Use exactly one SCREEN_TYPE line, one REASONING line, one ACTION line, and one GOAL_UPDATE block.
- SCREEN_TYPE must be exactly one allowed token such as `title`, `startup_menu`, `dialogue`, `battle`, `overworld`, or `indoor`; never write phrases like `title screen` or `main menu`.
- ACTION must be exactly one allowed token such as `start`, `a`, `b`, `up`, or `wait`; never write a sentence there.
- If you do not need a goal update, write exactly: GOAL_UPDATE: none

A one-token reply like "a", "b", "up", or "wait" is invalid.
REASONING must be a real sentence grounded in the current screenshot/state, not just a repeated action token.

Example response:
SCREEN_TYPE: indoor
REASONING: I still have no Pokemon, so the top todo is to leave the current building and follow the mandatory opening route.
ACTION: up
GOAL_UPDATE: none

Another good movement example:
SCREEN_TYPE: indoor
REASONING: This is an indoor room. Down is mostly black void and does not show continuous floor, so it is not walkable. Up and left still show visible floor tiles, so I should search across the visible room instead of moving into black space.
ACTION: up
GOAL_UPDATE: none

Good naming-screen example:
SCREEN_TYPE: naming_screen
REASONING: The cursor is still on the same letter after entering one character, so pressing A again would just repeat that letter. I should move right to choose a different character.
ACTION: right
GOAL_UPDATE: none

Bad reasoning example to avoid:
REASONING: The player is near the bottom of the screen, so the room probably extends downward into the black area.
This is wrong because camera position does not prove walkable floor, and black space is not visible floor.
"""

    # Accept exact prompt labels plus common equivalent spacing/colon variants.
    _FIELD_RE = re.compile(
        "^\\s*(screen(?:_|\\s+)type|reasoning|action|goal(?:_|\\s+)update)\\s*(?:\\:|\\uff1a)\\s*(.*)\\s*$",
        flags=re.IGNORECASE,
    )

    def __init__(self):
        """Initialize main agent."""
        self.logger = get_logger('MainAgent')
        self.config = get_config()
        self.client = AIClient(logger=self.logger)

        self.model = self.config.get('ai.agents.main.model')
        self.temperature = self.config.get('ai.agents.main.temperature')
        self.decision_max_tokens = min(
            int(self.config.get('ai.max_tokens', 4096) or 4096),
            int(self.config.get('ai.decision_max_tokens', 320) or 320),
        )
        self.strict_response_format = bool(
            self.config.get('decision.strict_response_format', True)
        )
        self._api_failure_count = 0
        self._api_cooldown_until = 0.0

        # Sub-components
        self.context = ContextManager(
            max_turns=self.config.get('memory.max_context_turns', 100),
            keep_recent=self.config.get('memory.keep_recent_turns', 20)
        )
        self.summarizer = Summarizer()
        self.goals = GoalManager()
        self.goals.set_long_term_goal(
            self.config.get(
                'goals.primary_goal',
                "Complete Pokemon Red by defeating the Elite Four and Champion"
            )
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

        if time.time() < self._api_cooldown_until:
            remaining = max(0.0, self._api_cooldown_until - time.time())
            if self._should_retry_same_turn():
                raise AIDecisionRetrySignal(
                    f"API cooldown active for {remaining:.1f}s after recent request failures",
                    source="ai_cooldown",
                    retry_after_seconds=remaining,
                )
            return {
                "action": "wait",
                "reasoning": f"API cooldown active for {remaining:.1f}s after recent request failures",
                "goal_update": None,
                "recorded_in_context": False,
                "decision_source": "ai_cooldown",
                "decision_path": "ai",
            }

        # Refresh the staged plan before prompting the model.
        self.goals.sync_with_game_state(game_state)

        # Check if we need summarization
        if self.context.needs_summarization():
            self.logger.info("Triggering context summarization")
            self._summarize_context()

        # Build prompt
        prompt = self._build_prompt(game_state, state_text, has_screenshot=bool(screenshot_bytes))

        # Get AI response
        try:
            response_text = self._request_model_response(
                prompt,
                screenshot_bytes,
                max_tokens=self.decision_max_tokens,
            )
            self.logger.debug(f"Raw model response (truncated): {response_text[:800]!r}")

            # Parse response
            decision = self._parse_response(response_text)
            if self._decision_needs_repair(decision, response_text):
                self.logger.warning("Model response was too terse or missing required fields; requesting repair")
                repaired_response = self._request_model_response(
                    self._build_repair_prompt(prompt, response_text),
                    screenshot_bytes,
                    max_tokens=self.decision_max_tokens,
                    temperature=min(float(self.temperature or 0.0), 0.2),
                )
                self.logger.debug(f"Repaired model response (truncated): {repaired_response[:800]!r}")
                decision = self._parse_response(repaired_response)
                response_text = repaired_response

            if self.strict_response_format and self._decision_is_invalid_after_repair(decision, response_text):
                raise ValueError("Model response remained invalid after repair")

            # Log decision
            self.logger.decision(decision['action'], decision['reasoning'])
            self._api_failure_count = 0
            self._api_cooldown_until = 0.0

            # Add to context
            self.context.add_turn(
                turn_number=turn,
                state=game_state,
                action=decision['action'],
                screen_type=decision.get('screen_type'),
                reasoning=decision['reasoning'],
                decision_source=decision.get('decision_source', 'ai'),
                decision_path=decision.get('decision_path', 'ai'),
            )

            # Update goals if needed
            if decision.get('goal_update') and decision['goal_update'] != 'none':
                self._process_goal_update(decision['goal_update'])

            return decision

        except Exception as e:
            self.logger.error(f"Failed to get AI decision: {e}")
            self._register_api_failure(str(e))
            if self._should_retry_same_turn() and self._is_retryable_decision_error(e):
                raise AIDecisionRetrySignal(
                    str(e),
                    source="ai_error",
                    retry_after_seconds=self.get_api_cooldown_remaining(),
                ) from e
            # Return safe default action
            return {
                'action': 'wait',
                'reasoning': f'Error occurred: {e}',
                'goal_update': None,
                'recorded_in_context': False,
                'decision_source': 'ai_error',
                'decision_path': 'ai',
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
            parts.append("A current raw game screenshot (PNG) is attached. No harness-side CV interpretation is provided; inspect the screenshot directly.")
        else:
            parts.append("No screenshot is attached this turn; rely on memory fields only.")

        # Add decision request
        parts.append("Decide the next single input.")
        parts.append(
            "Return exactly 4 non-empty plain-text lines and nothing else:\n"
            "SCREEN_TYPE: <one allowed token>\n"
            "REASONING: <one concrete sentence grounded in the screenshot/state>\n"
            "ACTION: <one allowed token>\n"
            "GOAL_UPDATE: <none or update commands>"
        )
        parts.append(
            "Allowed SCREEN_TYPE tokens: startup, title, startup_menu, options_menu, dialogue, "
            "cutscene, text_entry, naming_screen, battle, menu, overworld, indoor, unknown.\n"
            "Allowed ACTION tokens: up, down, left, right, a, b, start, select, wait."
        )
        parts.append(
            "Formatting traps to avoid: no markdown, no bullets, no JSON, no code fences, "
            "no extra blank lines, and no prose labels like 'title screen' or 'main menu' when an exact token exists."
        )

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

    def _request_model_response(
        self,
        prompt: str,
        screenshot_bytes: Optional[bytes],
        *,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Submit one multimodal request to the configured main model."""
        response = self.client.create_message(
            model=self.model,
            messages=[{
                "role": "user",
                "content": self._build_content(prompt, screenshot_bytes)
            }],
            max_tokens=max_tokens or self.config.get('ai.max_tokens', 4096),
            temperature=self.temperature if temperature is None else temperature,
            system=self.SYSTEM_PROMPT,
        )
        return response.content[0].text

    def _build_repair_prompt(self, prompt: str, previous_response: str) -> str:
        """Ask the same model to restate its answer in the required structured format."""
        return (
            f"{prompt}\n\n"
            "Your previous answer did not satisfy the required output format or was too terse.\n"
            "Rewrite it now as exactly 4 lines and keep the intended decision grounded in the same screenshot/state.\n"
            "Rules:\n"
            "- Use exactly these labels once each: SCREEN_TYPE, REASONING, ACTION, GOAL_UPDATE.\n"
            "- SCREEN_TYPE must be one allowed token.\n"
            "- ACTION must be one allowed token.\n"
            "- REASONING must be a complete sentence with concrete evidence, not just an action token.\n"
            "- Output plain text only with no bullets, code fences, JSON, or extra commentary.\n"
            "- If no goal update is needed, write GOAL_UPDATE: none.\n\n"
            f"Previous invalid answer:\n{previous_response}"
        )

    def _decision_needs_repair(self, decision: Dict[str, Any], raw_response: str) -> bool:
        """Return True when the model response should be retried for structure/quality."""
        response = raw_response or ""
        has_screen_type = bool(re.search("(?im)^\\s*screen(?:_|\\s+)type\\s*(?:\\:|\\uff1a)", response))
        has_reasoning = bool(re.search("(?im)^\\s*reasoning\\s*(?:\\:|\\uff1a)", response))
        has_action = bool(re.search("(?im)^\\s*action\\s*(?:\\:|\\uff1a)", response))
        has_goal_update = bool(re.search("(?im)^\\s*goal(?:_|\\s+)update\\s*(?:\\:|\\uff1a)", response))

        if not has_screen_type or not has_reasoning or not has_action or not has_goal_update:
            return True

        reasoning = (decision.get("reasoning") or "").strip()
        return self._reasoning_is_too_brief(reasoning)

    def _reasoning_is_too_brief(self, reasoning: str) -> bool:
        """Detect unusably terse explanations like a single action token."""
        cleaned = re.sub(r"\s+", " ", (reasoning or "")).strip().strip("`\"'")
        if not cleaned:
            return True

        lowered = cleaned.lower()
        if lowered in self.VALID_ACTIONS or lowered in self.VALID_SCREEN_TYPES:
            return True

        latin_tokens = re.findall(r"[a-zA-Z0-9]+", cleaned)
        cjk_chars = re.findall(r"[\u4e00-\u9fff]", cleaned)
        if len(cleaned) < 18 and len(latin_tokens) < 4 and len(cjk_chars) < 8:
            return True

        return False

    def _should_retry_same_turn(self) -> bool:
        """Whether transient AI failures should be retried on the same observation."""
        return bool(
            self.config.get('decision.pure_llm_mode', False)
            and self.config.get('decision.retry_same_turn_on_ai_error', True)
        )

    def _is_retryable_decision_error(self, error: Exception) -> bool:
        """Classify retryable transport/schema failures without masking config bugs."""
        message = str(error or "").lower()

        if "model response remained invalid after repair" in message:
            return True

        transient_tokens = (
            "status 429",
            "status 500",
            "status 502",
            "status 503",
            "status 504",
            "timeout",
            "timed out",
            "transport failure",
            "request failed",
            "invalid ai response",
            "unsupported ai response shape",
            "token",
        )
        return any(token in message for token in transient_tokens)

    def _decision_is_invalid_after_repair(self, decision: Dict[str, Any], raw_response: str) -> bool:
        """Reject malformed structured output when strict parsing is enabled."""
        if self._decision_needs_repair(decision, raw_response):
            return True
        if decision.get("action") not in self.VALID_ACTIONS:
            return True
        if decision.get("screen_type") not in self.VALID_SCREEN_TYPES:
            return True
        raw_action = str(decision.get("_raw_action") or "").strip().lower()
        raw_screen_type = str(decision.get("_raw_screen_type") or "").strip().lower()
        if raw_action and decision.get("action") == "wait" and raw_action != "wait":
            return True
        if raw_screen_type and decision.get("screen_type") == "unknown" and raw_screen_type != "unknown":
            return True
        return False

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
        screen_type_raw: Optional[str] = None
        goal_update: Optional[str] = None

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            match = self._FIELD_RE.match(line)
            if not match:
                i += 1
                continue

            field = match.group(1).lower().replace(" ", "_")
            value = (match.group(2) or "").strip()

            if field == "screen_type":
                if value:
                    screen_type_raw = value
                else:
                    screen_type_raw = self._collect_next_value_line(lines, i + 1)

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
                    continuation, i = self._collect_multiline_field(lines, i + 1, separator="\n")
                    goal_update = value if not continuation else f"{value}\n{continuation}"
                    continue
                goal_update, i = self._collect_multiline_field(lines, i + 1, separator="\n")
                continue

            i += 1

        action = self._normalize_action(action_raw)
        if not action and not self.strict_response_format:
            action = self._infer_action_from_text(response)
        if action not in self.VALID_ACTIONS:
            action = "wait"
        screen_type = self._normalize_screen_type(screen_type_raw)
        if not screen_type and not self.strict_response_format:
            screen_type = self._infer_screen_type_from_text(response)
        if not screen_type:
            screen_type = "unknown"

        if goal_update:
            goal_update = goal_update.strip()
            if goal_update.lower() == "none":
                goal_update = None

        if not reasoning:
            reasoning = response
        reasoning = self._compact_text(reasoning, max_chars=400)

        return {
            "screen_type": screen_type,
            "reasoning": reasoning,
            "action": action,
            "goal_update": goal_update,
            "recorded_in_context": True,
            "decision_source": "ai",
            "decision_path": "ai",
            "_raw_action": action_raw,
            "_raw_screen_type": screen_type_raw,
        }

    def _collect_multiline_field(
        self,
        lines: List[str],
        start_index: int,
        separator: str = " ",
    ) -> tuple[str, int]:
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
        return separator.join(collected).strip(), i

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

    def _normalize_screen_type(self, screen_type: Optional[str]) -> Optional[str]:
        """Normalize a raw screen-type label to a supported token."""
        if not screen_type:
            return None

        cleaned = screen_type.strip().strip("`\"'").lower()
        aliases = {
            "boot": "startup",
            "bootup": "startup",
            "intro": "cutscene",
            "intro_cutscene": "cutscene",
            "cutscene_dialogue": "dialogue",
            "text": "dialogue",
            "textbox": "dialogue",
            "text_box": "dialogue",
            "text-entry": "text_entry",
            "text entry": "text_entry",
            "naming": "naming_screen",
            "name_entry": "naming_screen",
            "name screen": "naming_screen",
            "title_screen": "title",
            "title screen": "title",
            "main_menu": "startup_menu",
            "main menu": "startup_menu",
            "new game menu": "startup_menu",
            "startup menu": "startup_menu",
            "options": "options_menu",
            "over world": "overworld",
            "indoors": "indoor",
            "world": "overworld",
        }
        cleaned = aliases.get(cleaned, cleaned.replace("-", "_").replace(" ", "_"))
        if cleaned in self.VALID_SCREEN_TYPES:
            return cleaned
        return None

    def _infer_screen_type_from_text(self, response: str) -> str:
        """Best-effort fallback when SCREEN_TYPE is missing."""
        text = (response or "").lower()
        if (
            "rival's name" in text
            or "your name" in text
            or "what is your name" in text
            or "naming screen" in text
            or "命名" in text
            or "起名" in text
            or "名字" in text
            or "姓名" in text
        ):
            return "naming_screen"
        if (
            "title screen" in text
            or "press start" in text
            or "标题画面" in text
            or "标题界面" in text
            or "标题屏" in text
        ):
            return "title"
        if (
            ("new game" in text and "option" in text)
            or "new game" in text
            or "新游戏" in text
            or "主菜单" in text
        ):
            return "startup_menu"
        if "options menu" in text or "选项菜单" in text or "设置菜单" in text:
            return "options_menu"
        if (
            "dialogue" in text
            or "text box" in text
            or "对话" in text
            or "对白" in text
            or "对话框" in text
            or "文本框" in text
            or "台词" in text
        ):
            return "dialogue"
        if (
            "cutscene" in text
            or "scripted intro" in text
            or "non-interactive" in text
            or "开场" in text
            or "序章" in text
            or "过场" in text
            or "剧情" in text
            or "大木博士" in text
            or "oak intro" in text
        ):
            return "cutscene"
        if "battle" in text or "战斗" in text:
            return "battle"
        if "menu" in text or "菜单" in text:
            return "menu"
        if (
            "overworld" in text
            or "outside" in text
            or "室外" in text
            or "外面" in text
            or "城镇" in text
        ):
            return "overworld"
        if (
            "indoor" in text
            or "room" in text
            or "house" in text
            or "室内" in text
            or "房间" in text
            or "屋内" in text
            or "家里" in text
        ):
            return "indoor"
        return "unknown"

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
        self.goals.apply_update_text(update_text)

    def record_external_decision(
        self,
        game_state: Dict[str, Any],
        action: str,
        reasoning: str,
        goal_update: Optional[str] = None,
        screen_type: Optional[str] = None,
        decision_source: Optional[str] = None,
        decision_path: Optional[str] = None,
    ) -> None:
        """Record a non-main-model decision in context so recovery tools can see it."""
        self.context.add_turn(
            turn_number=game_state["turn"],
            state=game_state,
            action=action,
            screen_type=screen_type,
            reasoning=self._compact_text(reasoning, max_chars=400),
            decision_source=decision_source,
            decision_path=decision_path,
        )
        if goal_update and goal_update != "none":
            self._process_goal_update(goal_update)

    def record_action_outcome(self, result: str) -> None:
        """Attach the observed outcome of the latest action."""
        self.context.update_last_turn_result(result)

    def add_guidance_note(self, note: str, source: str = "critic") -> None:
        """Store a short external guidance note inside context."""
        self.context.add_note(note, source=source)

    def is_in_api_cooldown(self) -> bool:
        """Return whether temporary API backoff is active."""
        return time.time() < self._api_cooldown_until

    def get_api_cooldown_remaining(self) -> float:
        """Return remaining cooldown seconds."""
        return max(0.0, self._api_cooldown_until - time.time())

    def _register_api_failure(self, error_text: str) -> None:
        """Back off after repeated or rate-limited API failures."""
        message = (error_text or "").lower()
        if not any(token in message for token in ("status 429", "status 500", "status 502", "status 503", "status 504", "token", "timeout")):
            return

        self._api_failure_count += 1
        base = float(self.config.get("ai.api_error_cooldown_seconds", 6) or 6)
        max_cooldown = float(self.config.get("ai.api_error_cooldown_max_seconds", 30) or 30)
        cooldown = min(max_cooldown, base * max(1, self._api_failure_count))
        self._api_cooldown_until = max(self._api_cooldown_until, time.time() + cooldown)

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
