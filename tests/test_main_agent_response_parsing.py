import unittest

from src.agents.main_agent import MainAgent


class MainAgentResponseParsingTests(unittest.TestCase):
    def _build_agent(self, *, strict=True):
        agent = object.__new__(MainAgent)
        agent.strict_response_format = strict
        agent.action_plan_enabled = False
        agent.action_plan_max_actions = 0
        agent.config = type(
            "_ConfigStub",
            (),
            {"get": lambda self, key, default=None: default},
        )()
        return agent

    def test_strict_mode_does_not_infer_missing_action_field(self):
        agent = self._build_agent(strict=True)

        decision = agent._parse_response(
            "SCREEN_TYPE: title\n"
            "REASONING: The title screen is visible and the next step should be Start.\n"
            "GOAL_UPDATE: none"
        )

        self.assertEqual(decision["screen_type"], "title")
        self.assertEqual(decision["action"], "wait")

    def test_non_strict_mode_can_infer_action_from_reasoning_text(self):
        agent = self._build_agent(strict=False)

        decision = agent._parse_response(
            "SCREEN_TYPE: title\n"
            "REASONING: The title screen is visible, so I should press start to continue.\n"
            "GOAL_UPDATE: none"
        )

        self.assertEqual(decision["action"], "start")

    def test_title_screen_alias_is_normalized_to_title(self):
        agent = self._build_agent(strict=True)

        decision = agent._parse_response(
            "SCREEN_TYPE: title screen\n"
            "REASONING: The title screen is visible, so Start should continue.\n"
            "ACTION: start\n"
            "GOAL_UPDATE: none"
        )

        self.assertEqual(decision["screen_type"], "title")

    def test_parser_accepts_spaced_labels_and_fullwidth_colon(self):
        agent = self._build_agent(strict=True)

        decision = agent._parse_response(
            "SCREEN TYPE：startup_menu\n"
            "REASONING：The new game menu is visible, so confirming it is the next step.\n"
            "ACTION：a\n"
            "GOAL UPDATE：none"
        )

        self.assertEqual(decision["screen_type"], "startup_menu")
        self.assertEqual(decision["action"], "a")

    def test_wait_action_is_rejected_in_strict_mode_after_repair(self):
        agent = self._build_agent(strict=True)
        response = (
            "SCREEN_TYPE: dialogue\n"
            "REASONING: A visible dialogue box is still open, but WAIT is not allowed.\n"
            "ACTION: wait\n"
            "GOAL_UPDATE: none"
        )

        decision = agent._parse_response(response)

        self.assertTrue(agent._decision_is_invalid_after_repair(decision, response))


if __name__ == "__main__":
    unittest.main()
