import unittest

from src.agents.main_agent import MainAgent
from src.memory.context_manager import ContextManager
from src.tools.goal_manager import GoalManager


class _ConfigStub:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)


class MainAgentPromptingTests(unittest.TestCase):
    def _build_agent(self, *, config=None, keep_recent=12):
        agent = object.__new__(MainAgent)
        agent.config = _ConfigStub(config or {})
        agent.action_plan_enabled = True
        agent.action_plan_max_actions = 4
        agent.context = ContextManager(max_turns=80, keep_recent=keep_recent)
        agent.goals = GoalManager()
        return agent

    def test_llm_primary_prompt_allows_short_movement_action_plan(self):
        agent = self._build_agent(
            config={
                "decision.llm_primary_mode": True,
                "decision.llm_primary_action_plan_enabled": True,
            }
        )

        prompt = agent._build_prompt({"turn": 1}, "STATE", False)

        self.assertIn("2-3 movement actions", prompt)
        self.assertIn("Immediate movement preference/cautions", agent.SYSTEM_PROMPT)

    def test_refresh_task_notebook_populates_focus_progress_and_avoid(self):
        agent = self._build_agent()
        agent.goals.set_focus("Leave the current house and reach the road.", source="system")
        agent.goals.add_todo(
            "Go downstairs and exit through the front door.",
            source="system",
            front=True,
        )
        agent.context.add_turn(
            1,
            {},
            action="left",
            screen_type="indoor",
            reasoning="Blocked movement",
            result="After left: position did not change",
        )
        agent.context.add_turn(
            2,
            {},
            action="up",
            screen_type="indoor",
            reasoning="Advance toward the exit",
            result="After up: moved from (7,6) to (7,5) on map 37",
        )

        agent._refresh_task_notebook()
        context = agent.context.get_context_for_ai()

        self.assertIn("=== TASK NOTE ===", context)
        self.assertIn("FOCUS_NOW: Leave the current house and reach the road.", context)
        self.assertIn("NEXT_STEP: Go downstairs and exit through the front door.", context)
        self.assertIn("RECENT_PROGRESS: After up: moved from (7,6) to (7,5) on map 37", context)
        self.assertIn("AVOID_REPEAT: Do not blindly repeat left", context)

    def test_refresh_task_notebook_allows_repeat_after_facing_change(self):
        agent = self._build_agent()
        agent.goals.set_focus("Leave Oak's Lab and head north.", source="system")
        agent.context.add_turn(
            1,
            {},
            action="left",
            screen_type="overworld",
            reasoning="Step off the lab frontage",
            result="After left: position did not change but facing changed from down to left",
        )

        agent._refresh_task_notebook()
        context = agent.context.get_context_for_ai()

        self.assertIn("AVOID_REPEAT: A left press only changed facing", context)
        self.assertIn("repeating it once is valid", context)

    def test_context_prompt_only_renders_recent_turn_window(self):
        context = ContextManager(max_turns=80, keep_recent=2)
        for turn in range(1, 6):
            context.add_turn(
                turn,
                {},
                action="up",
                screen_type="indoor",
                reasoning=f"Reasoning {turn}",
                result=f"Result {turn}",
            )

        prompt_context = context.get_context_for_ai()

        self.assertNotIn("Turn 1:", prompt_context)
        self.assertNotIn("Turn 2:", prompt_context)
        self.assertIn("Turn 4:", prompt_context)
        self.assertIn("Turn 5:", prompt_context)


if __name__ == "__main__":
    unittest.main()
