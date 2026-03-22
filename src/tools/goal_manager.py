"""Goal and todo manager for staged Pokemon Red progression."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..utils.logger import get_logger


def _now_iso() -> str:
    """Return a stable ISO timestamp."""
    return datetime.now().isoformat()


def _normalize_text(text: str) -> str:
    """Normalize text for fuzzy todo matching."""
    return " ".join((text or "").strip().lower().split())


@dataclass
class Goal:
    """Represents a high-level operational goal."""

    goal_type: str
    description: str
    created_at: str
    completed: bool = False
    completed_at: Optional[str] = None


@dataclass
class TodoItem:
    """Represents a live todo item."""

    description: str
    created_at: str
    source: str = "system"
    completed: bool = False
    completed_at: Optional[str] = None


class GoalManager:
    """Manage staged goals, current focus, and a live todo list."""

    DEFAULT_LONG_TERM_GOAL = (
        "Complete Pokemon Red by defeating the Elite Four and becoming Champion."
    )
    BATTLE_TODO = "Finish the current battle safely before returning to movement."
    EXPLORATION_TODO = "Explore unseen tiles systematically until you find the door, stairs, or story trigger."

    def __init__(self):
        """Initialize goal manager."""
        self.logger = get_logger("GoalManager")

        self.long_term_goal: str = self.DEFAULT_LONG_TERM_GOAL
        self.primary_goal: Optional[Goal] = None
        self.secondary_goal: Optional[Goal] = None
        self.tertiary_goal: Optional[Goal] = None
        self.focus: Optional[str] = None

        self.todo_items: List[TodoItem] = []
        self.completed_goals: List[Goal] = []
        self.completed_todos: List[TodoItem] = []

        self.current_stage: Optional[str] = None
        self.initial_map_id: Optional[int] = None
        self.visited_maps: List[int] = []
        self.last_snapshot: Dict[str, Any] = {}

        self.logger.info("Goal manager initialized")

    def set_long_term_goal(self, description: str) -> None:
        """Set the long-term mission."""
        cleaned = (description or "").strip()
        if cleaned:
            self.long_term_goal = cleaned
            self.logger.milestone(f"LONG-TERM MISSION: {cleaned}")

    def set_primary_goal(self, description: str) -> None:
        """Set the current primary goal."""
        self.primary_goal = self._set_goal(self.primary_goal, "primary", description)

    def set_secondary_goal(self, description: str) -> None:
        """Set the current secondary goal."""
        self.secondary_goal = self._set_goal(self.secondary_goal, "secondary", description)

    def set_tertiary_goal(self, description: str) -> None:
        """Set the current tertiary goal."""
        self.tertiary_goal = self._set_goal(self.tertiary_goal, "tertiary", description)

    def set_focus(self, description: Optional[str], source: str = "system") -> None:
        """Set the immediate focus."""
        cleaned = (description or "").strip()
        if not cleaned:
            return
        if self.focus == cleaned:
            return
        self.focus = cleaned
        self.logger.info(f"NEW FOCUS ({source.upper()}): {cleaned}")

    def clear_focus(self) -> None:
        """Clear the immediate focus."""
        self.focus = None

    def add_todo(
        self,
        description: str,
        source: str = "system",
        front: bool = False,
    ) -> None:
        """Add a todo item unless it already exists."""
        cleaned = (description or "").strip()
        if not cleaned:
            return

        needle = _normalize_text(cleaned)
        for todo in self.todo_items:
            if not todo.completed and _normalize_text(todo.description) == needle:
                return

        item = TodoItem(description=cleaned, created_at=_now_iso(), source=source)
        if front:
            self.todo_items.insert(0, item)
        else:
            self.todo_items.append(item)
        self.logger.info(f"NEW TODO ({source.upper()}): {cleaned}")

    def complete_todo(self, description: str) -> bool:
        """Mark the first matching todo as completed."""
        match = self._find_todo(description)
        if not match:
            return False

        self.todo_items.remove(match)
        match.completed = True
        match.completed_at = _now_iso()
        self.completed_todos.append(match)
        self.logger.milestone(f"COMPLETED TODO: {match.description}")
        return True

    def remove_todo(self, description: str) -> bool:
        """Remove a pending todo without marking it completed."""
        match = self._find_todo(description)
        if not match:
            return False
        self.todo_items.remove(match)
        self.logger.info(f"REMOVED TODO: {match.description}")
        return True

    def sync_with_game_state(self, game_state: Dict[str, Any]) -> None:
        """Refresh the staged plan from current game progress."""
        memory = game_state.get("memory", {})
        if not memory:
            return
        pre_world = bool(game_state.get("pre_world"))
        screen_type = str((game_state.get("visual", {}) or {}).get("screen_type") or "").strip().lower()
        scripted_intro = bool(pre_world or (
            game_state.get("pre_starter_script")
            and screen_type in {
                "startup",
                "title",
                "startup_menu",
                "options_menu",
                "dialogue",
                "cutscene",
                "text_entry",
                "naming_screen",
            }
        ))

        position = memory.get("position", {})
        map_id = position.get("map_id")
        if not scripted_intro and map_id is not None and self.initial_map_id is None:
            self.initial_map_id = map_id
        if not scripted_intro and map_id is not None and map_id not in self.visited_maps:
            self.visited_maps.append(map_id)

        previous_party_count = int(self.last_snapshot.get("party_count", 0))
        previous_badges = int(self.last_snapshot.get("badge_count", 0))
        party_count = len(memory.get("party", []))
        badge_count = int(memory.get("badge_count", 0))
        in_battle = bool(memory.get("in_battle", False))
        deltas = game_state.get("deltas", {})
        exploration = game_state.get("exploration", {})
        movement_stall_turns = int(deltas.get("movement_stall_turns", 0) or 0)
        nearby_unexplored = exploration.get("nearby_unexplored", [])

        stage = self._determine_stage(memory, pre_world=scripted_intro)
        stage_changed = stage != self.current_stage
        if stage_changed:
            self.current_stage = stage
            self._apply_stage_template(stage, memory)

        if stage == "pre_starter":
            self._sync_pre_starter_focus(memory)

        if previous_party_count == 0 and party_count > 0:
            self._record_completed_milestone("Obtained the first Pokemon.")
            if stage == "early_game":
                self.set_focus(
                    "Finish any remaining intro battle or dialogue, then leave and follow the main route.",
                    source="system",
                )

        if badge_count > previous_badges:
            self._record_completed_milestone("Earned a new badge.")
            if stage == "gym_progress":
                self.set_focus(
                    "Use the new badge progress to push the next mandatory route or town checkpoint.",
                    source="system",
                )

        self._sync_battle_todo(in_battle)
        if scripted_intro:
            self.remove_todo(self.EXPLORATION_TODO)
        else:
            self._sync_exploration_focus(
                stage=stage,
                in_battle=in_battle,
                movement_stall_turns=movement_stall_turns,
                nearby_unexplored=nearby_unexplored,
            )

        self.last_snapshot = {
            "party_count": party_count,
            "badge_count": badge_count,
            "map_id": map_id,
            "in_battle": in_battle,
        }

    def apply_update_text(self, update_text: str) -> None:
        """Apply AI-issued goal and todo updates."""
        for raw_line in self._iter_update_lines(update_text):
            if ":" not in raw_line:
                continue

            key, value = raw_line.split(":", 1)
            command = key.strip().upper()
            payload = value.strip()
            if not payload:
                continue

            if command == "PRIMARY":
                self.set_primary_goal(payload)
            elif command == "SECONDARY":
                self.set_secondary_goal(payload)
            elif command == "TERTIARY":
                self.set_tertiary_goal(payload)
            elif command == "FOCUS":
                self.set_focus(payload, source="ai")
            elif command in {"ADD_TODO", "ADD"}:
                self.add_todo(payload, source="ai")
            elif command in {"NEXT_TODO", "NEXT"}:
                self.add_todo(payload, source="ai", front=True)
            elif command in {"DONE_TODO", "DONE"}:
                self.complete_todo(payload)
            elif command in {"REMOVE_TODO", "REMOVE"}:
                self.remove_todo(payload)
            elif command == "BLOCKED":
                self.add_todo(payload, source="ai", front=True)
                self.set_focus(f"Resolve blocker: {payload}", source="ai")

    def get_current_goals(self) -> Dict[str, Optional[str]]:
        """Return the current structured goals for compatibility."""
        return {
            "long_term": self.long_term_goal,
            "focus": self.focus,
            "primary": self.primary_goal.description if self.primary_goal else None,
            "secondary": self.secondary_goal.description if self.secondary_goal else None,
            "tertiary": self.tertiary_goal.description if self.tertiary_goal else None,
        }

    def get_dashboard_items(self, todo_limit: int = 6, done_limit: int = 3) -> List[Dict[str, str]]:
        """Return dashboard-ready items."""
        items: List[Dict[str, str]] = []

        if self.focus:
            items.append({"type": "focus", "description": self.focus, "status": "active"})
        if self.primary_goal:
            items.append(
                {
                    "type": "primary",
                    "description": self.primary_goal.description,
                    "status": "active",
                }
            )
        if self.secondary_goal:
            items.append(
                {
                    "type": "secondary",
                    "description": self.secondary_goal.description,
                    "status": "active",
                }
            )
        if self.tertiary_goal:
            items.append(
                {
                    "type": "tertiary",
                    "description": self.tertiary_goal.description,
                    "status": "active",
                }
            )

        for index, todo in enumerate(self.todo_items[:todo_limit], start=1):
            items.append(
                {
                    "type": f"todo {index}",
                    "description": todo.description,
                    "status": "pending",
                }
            )

        for todo in reversed(self.completed_todos[-done_limit:]):
            items.append(
                {
                    "type": "done",
                    "description": todo.description,
                    "status": "completed",
                }
            )

        return items

    def get_goals_text(self) -> str:
        """Return prompt text with mission, focus, and live todo."""
        lines = [
            "=== LIVE PLAN ===",
            f"LONG_TERM_MISSION: {self.long_term_goal}",
            f"CURRENT_STAGE: {self.current_stage or 'unknown'}",
            f"FOCUS: {self.focus or 'Not set'}",
            "",
            "OPERATING GOALS:",
            f"PRIMARY: {self.primary_goal.description if self.primary_goal else 'Not set'}",
            f"SECONDARY: {self.secondary_goal.description if self.secondary_goal else 'Not set'}",
            f"TERTIARY: {self.tertiary_goal.description if self.tertiary_goal else 'Not set'}",
            "",
            "LIVE TODO:",
        ]

        if self.todo_items:
            for index, todo in enumerate(self.todo_items, start=1):
                lines.append(f"{index}. [ ] {todo.description}")
        else:
            lines.append("1. [ ] No todo set")

        if self.completed_todos:
            lines.append("")
            lines.append("RECENTLY COMPLETED TODO:")
            for todo in self.completed_todos[-3:]:
                lines.append(f"- [x] {todo.description}")

        return "\n".join(lines)

    def save(self, filepath: str) -> None:
        """Persist all goal and todo state."""
        data = {
            "long_term_goal": self.long_term_goal,
            "primary": self._goal_to_dict(self.primary_goal),
            "secondary": self._goal_to_dict(self.secondary_goal),
            "tertiary": self._goal_to_dict(self.tertiary_goal),
            "focus": self.focus,
            "current_stage": self.current_stage,
            "initial_map_id": self.initial_map_id,
            "visited_maps": self.visited_maps,
            "todo_items": [asdict(todo) for todo in self.todo_items],
            "completed_goals": [self._goal_to_dict(goal) for goal in self.completed_goals],
            "completed_todos": [asdict(todo) for todo in self.completed_todos],
            "last_snapshot": self.last_snapshot,
        }

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

        self.logger.debug(f"Saved goals to {filepath}")

    def load(self, filepath: str) -> None:
        """Restore goal and todo state."""
        if not Path(filepath).exists():
            self.logger.warning(f"Goals file not found: {filepath}")
            return

        with open(filepath, "r", encoding="utf-8") as file:
            data = json.load(file)

        self.long_term_goal = data.get("long_term_goal", self.DEFAULT_LONG_TERM_GOAL)
        self.primary_goal = self._dict_to_goal(data.get("primary"))
        self.secondary_goal = self._dict_to_goal(data.get("secondary"))
        self.tertiary_goal = self._dict_to_goal(data.get("tertiary"))
        self.focus = data.get("focus")
        self.current_stage = data.get("current_stage")
        self.initial_map_id = data.get("initial_map_id")
        self.visited_maps = data.get("visited_maps", [])
        self.todo_items = [TodoItem(**todo) for todo in data.get("todo_items", [])]
        self.completed_goals = [
            self._dict_to_goal(goal) for goal in data.get("completed_goals", []) if goal
        ]
        self.completed_todos = [
            TodoItem(**todo) for todo in data.get("completed_todos", [])
        ]
        self.last_snapshot = data.get("last_snapshot", {})

        self.logger.info(f"Loaded goals from {filepath}")

    def _set_goal(
        self,
        current_goal: Optional[Goal],
        goal_type: str,
        description: str,
    ) -> Goal:
        """Create a goal entry, completing the old one when it changes."""
        cleaned = (description or "").strip()
        if not cleaned:
            return current_goal or Goal(goal_type=goal_type, description="", created_at=_now_iso())

        if current_goal and _normalize_text(current_goal.description) == _normalize_text(cleaned):
            return current_goal

        if current_goal and current_goal.description and not current_goal.completed:
            self.complete_goal(goal_type)

        goal = Goal(goal_type=goal_type, description=cleaned, created_at=_now_iso())
        self.logger.info(f"NEW {goal_type.upper()} GOAL: {cleaned}")
        return goal

    def complete_goal(self, goal_type: str) -> None:
        """Mark an operational goal as completed."""
        goal = None
        if goal_type == "primary":
            goal = self.primary_goal
        elif goal_type == "secondary":
            goal = self.secondary_goal
        elif goal_type == "tertiary":
            goal = self.tertiary_goal

        if goal and not goal.completed and goal.description:
            goal.completed = True
            goal.completed_at = _now_iso()
            self.completed_goals.append(goal)
            self.logger.milestone(f"COMPLETED {goal_type.upper()} GOAL: {goal.description}")

    def _determine_stage(self, memory: Dict[str, Any], pre_world: bool = False) -> str:
        """Choose the current progression stage."""
        if pre_world:
            return "startup"
        badge_count = int(memory.get("badge_count", 0))
        party_count = len(memory.get("party", []))

        if badge_count >= 8:
            return "league"
        if badge_count >= 1:
            return "gym_progress"
        if party_count == 0:
            return "pre_starter"
        return "early_game"

    def _apply_stage_template(self, stage: str, memory: Dict[str, Any]) -> None:
        """Replace the active stage plan."""
        if stage == "startup":
            self.set_primary_goal("Get through the boot, title, intro dialogue, and naming flow.")
            self.set_secondary_goal(
                "Use the screenshot itself to identify when to press A, Start, or directional inputs during the intro."
            )
            self.set_tertiary_goal(
                "Do not trust map coordinates or exploration memory until a real room or outdoor map appears."
            )
            self.set_focus(
                "The game is still in boot/title/intro. Ignore overworld navigation ideas and use the screenshot to progress into a real playable room.",
                source="system",
            )
            self._replace_todos(
                [
                    "Advance past the boot or title screen.",
                    "Start a new game if the main menu appears.",
                    "Advance the intro dialogue and any naming screens.",
                    "Reach the first real controllable in-game room.",
                ]
            )
            return

        if stage == "pre_starter":
            self.set_primary_goal("Get the first Pokemon and unlock the opening story route.")
            self.set_secondary_goal(
                "Exit the current room and building, then follow the mandatory opening script instead of checking optional furniture."
            )
            self.set_tertiary_goal(
                "If movement fails or a person blocks progress, face the blocker and press A, but ignore optional PC, TV, and bookshelf interactions unless they are clearly required."
            )
            self.set_focus(
                "Do not think about the Champion yet. First leave the room, leave the house, and obtain the first Pokemon. Ignore optional bedroom or house flavor interactions unless they clearly block progress. If the exit is not visible, explore unseen tiles until it appears.",
                source="system",
            )
            self._replace_todos(
                [
                    "Exit the current room.",
                    "Exit the house or current building.",
                    "Ignore optional bedroom PC, TV, and bookshelf interactions unless they clearly unlock progress.",
                    "If the exit or stairs is not visible, explore the room perimeter and unseen tiles until you find it.",
                    "Walk toward the first mandatory NPC or lab.",
                    "If a person or script blocks progress, face them and press A.",
                    "Obtain the first Pokemon.",
                ]
            )
            return

        if stage == "early_game":
            self.set_primary_goal(
                "Finish the mandatory early-game errands and set up for the first badge."
            )
            self.set_secondary_goal(
                "Advance along the main route, talking to blockers and accepting required dialogue."
            )
            self.set_tertiary_goal(
                "Heal when HP is low and avoid wasting turns in menus or random backtracking."
            )
            self.set_focus(
                "Push the next mandatory checkpoint one concrete step at a time. If the exit is not visible, explore unseen tiles systematically instead of pushing one blocked direction.",
                source="system",
            )
            self._replace_todos(
                [
                    "Finish any remaining intro battle or dialogue.",
                    "Leave the current building or town and follow the main route.",
                    "Talk to mandatory NPCs and accept required story items or instructions.",
                    "Heal if the lead Pokemon is low on HP.",
                    "Train safely before forced fights.",
                ]
            )
            return

        if stage == "gym_progress":
            self.set_primary_goal("Earn the next badge by clearing the next route, town, or gym step.")
            self.set_secondary_goal("Solve the immediate blocker before thinking about later gyms.")
            self.set_tertiary_goal("Keep the team healthy, stocked, and out of dead-end menus.")
            self.set_focus(
                "Identify the nearest mandatory blocker and resolve it with the smallest possible action sequence.",
                source="system",
            )
            self._replace_todos(
                [
                    "Resolve the current route, town, or dungeon blocker.",
                    "Reach the next major story checkpoint or gym.",
                    "Heal and restock before difficult fights.",
                    "Train only when underleveled for the next required battle.",
                    "Challenge the next gym when prepared.",
                ]
            )
            return

        self.set_primary_goal("Finish the endgame one hallway and one battle at a time.")
        self.set_secondary_goal("Preserve HP, PP, and items between major fights.")
        self.set_tertiary_goal("Avoid unnecessary movement, menus, and risky detours.")
        self.set_focus(
            "Stay narrow: clear the next room or battle cleanly, then reassess.",
            source="system",
        )
        self._replace_todos(
            [
                "Reach the next Elite Four or Champion battle.",
                "Heal or restore resources before the next major fight when possible.",
                "Finish the next required battle safely.",
            ]
        )

    def _replace_todos(self, descriptions: Iterable[str]) -> None:
        """Replace pending todos with a clean stage-specific list."""
        self.todo_items = []
        for description in descriptions:
            self.add_todo(description, source="system")

    def _find_todo(self, description: str) -> Optional[TodoItem]:
        """Find a todo by normalized or fuzzy matching."""
        needle = _normalize_text(description)
        if not needle:
            return None

        exact_match = None
        contains_match = None
        for todo in self.todo_items:
            if todo.completed:
                continue
            hay = _normalize_text(todo.description)
            if hay == needle:
                exact_match = todo
                break
            if needle in hay or hay in needle:
                contains_match = contains_match or todo
        return exact_match or contains_match

    def _sync_battle_todo(self, in_battle: bool) -> None:
        """Add or remove the battle todo overlay."""
        if in_battle:
            self.add_todo(self.BATTLE_TODO, source="system", front=True)
            self.set_focus("Finish the current battle safely before resuming exploration.", source="system")
            return

        if self.remove_todo(self.BATTLE_TODO):
            if self.current_stage:
                self._restore_stage_focus()

    def _sync_exploration_focus(
        self,
        stage: str,
        in_battle: bool,
        movement_stall_turns: int,
        nearby_unexplored: List[Any],
    ) -> None:
        """Bias the plan toward exploration when movement has stalled."""
        if in_battle:
            self.remove_todo(self.EXPLORATION_TODO)
            return

        should_explore = movement_stall_turns >= 2 and bool(nearby_unexplored)
        if should_explore:
            self.add_todo(self.EXPLORATION_TODO, source="system", front=True)
            self.set_focus(
                "The route is not obvious. Stop pushing the same wall and systematically explore unseen tiles to locate the real exit, door, or stairs.",
                source="system",
            )
            return

        if self.remove_todo(self.EXPLORATION_TODO) and self.current_stage:
            self._restore_stage_focus()

    def _sync_pre_starter_focus(self, memory: Dict[str, Any]) -> None:
        """Tighten early-story focus so the model leaves home instead of checking flavor objects."""
        position = memory.get("position", {})
        map_id = int(position.get("map_id", 0) or 0)

        if map_id == 38:
            self.set_focus(
                "You are still before the first Pokemon. Leave the bedroom by finding the stairs; do not waste turns on the PC, TV, or bookshelf unless a visible dialogue or blocker makes them mandatory.",
                source="system",
            )
            return

        if map_id == 37:
            self.set_focus(
                "You are still before the first Pokemon. Leave the house through the front door; ignore optional house furniture and flavor interactions unless they clearly block progress.",
                source="system",
            )
            return

    def _restore_stage_focus(self) -> None:
        """Restore the stage focus after a temporary override."""
        if self.current_stage == "startup":
            self.set_focus(
                "The game is still in boot/title/intro. Ignore overworld navigation ideas and use the screenshot to progress into a real playable room.",
                source="system",
            )
        elif self.current_stage == "pre_starter":
            self.set_focus(
                "Do not think about the Champion yet. First leave the room, leave the house, and obtain the first Pokemon. If the exit is not visible, explore unseen tiles until it appears.",
                source="system",
            )
        elif self.current_stage == "early_game":
            self.set_focus(
                "Push the next mandatory checkpoint one concrete step at a time. If the exit is not visible, explore unseen tiles systematically instead of pushing one blocked direction.",
                source="system",
            )
        elif self.current_stage == "gym_progress":
            self.set_focus(
                "Identify the nearest mandatory blocker and resolve it with the smallest possible action sequence.",
                source="system",
            )
        elif self.current_stage == "league":
            self.set_focus(
                "Stay narrow: clear the next room or battle cleanly, then reassess.",
                source="system",
            )

    def _record_completed_milestone(self, description: str) -> None:
        """Record a synthetic completed todo for a milestone."""
        normalized = _normalize_text(description)
        for todo in self.completed_todos:
            if _normalize_text(todo.description) == normalized:
                return
        self.completed_todos.append(
            TodoItem(
                description=description,
                created_at=_now_iso(),
                source="system",
                completed=True,
                completed_at=_now_iso(),
            )
        )
        self.logger.milestone(f"MILESTONE: {description}")

    def _iter_update_lines(self, update_text: str) -> Iterable[str]:
        """Yield stripped goal-update lines."""
        for raw_line in (update_text or "").splitlines():
            cleaned = raw_line.strip().lstrip("-").strip()
            if cleaned:
                yield cleaned

    def _goal_to_dict(self, goal: Optional[Goal]) -> Optional[Dict[str, Any]]:
        """Serialize a goal."""
        return asdict(goal) if goal else None

    def _dict_to_goal(self, data: Optional[Dict[str, Any]]) -> Optional[Goal]:
        """Deserialize a goal."""
        if not data:
            return None
        return Goal(**data)
