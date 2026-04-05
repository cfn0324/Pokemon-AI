import unittest

from main import PokemonAIAgent
from src.control.early_battle_controller import EarlyBattleController


class _ConfigStub:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)


def _state(
    *,
    in_battle=True,
    badge_count=0,
    party_size=1,
    menu_active=False,
    text_box_active=None,
    enemy_hp=18,
    battle_type="trainer",
    moves=None,
    battle_stall_turns=0,
):
    if text_box_active is None:
        text_box_active = not menu_active
    if moves is None:
        moves = [{"move_id": 10, "pp": 35}, {"move_id": 45, "pp": 40}]
    return {
        "battle_summary": {"battle_stall_turns": battle_stall_turns},
        "memory": {
            "in_battle": in_battle,
            "badge_count": badge_count,
            "ui": {"menu_active": menu_active, "text_box_active": text_box_active},
            "battle": {"enemy_current_hp": enemy_hp, "battle_type": battle_type},
            "party": [{"level": 6, "moves": list(moves)}] * party_size,
        }
    }


class EarlyBattleControllerTests(unittest.TestCase):
    def test_advances_battle_text_without_ai(self):
        controller = EarlyBattleController()

        decision = controller.maybe_decide(_state(menu_active=False), "battle")

        self.assertEqual(decision["action"], "a")

    def test_accepts_default_battle_menu_choice(self):
        controller = EarlyBattleController()

        decision = controller.maybe_decide(_state(menu_active=True, enemy_hp=18), "battle")

        self.assertEqual(decision["action"], "a")

    def test_wild_battle_menu_accepts_default_choice(self):
        controller = EarlyBattleController()

        decision = controller.maybe_decide(
            _state(menu_active=True, text_box_active=False, enemy_hp=18, battle_type="wild"),
            "battle",
        )

        self.assertEqual(decision["action"], "a")

    def test_wild_battle_advances_text_until_escape_menu_returns(self):
        controller = EarlyBattleController()

        decision = controller.maybe_decide(
            _state(menu_active=False, enemy_hp=18, battle_type="wild"),
            "battle",
        )

        self.assertEqual(decision["action"], "a")

    def test_wild_battle_textbox_overrides_stale_menu_overlay(self):
        controller = EarlyBattleController()

        decision = controller.maybe_decide(
            _state(menu_active=True, text_box_active=True, enemy_hp=18, battle_type="wild"),
            "battle",
        )

        self.assertEqual(decision["action"], "a")

    def test_closes_stale_menu_after_enemy_faints(self):
        controller = EarlyBattleController()

        decision = controller.maybe_decide(_state(menu_active=True, enemy_hp=0), "battle")

        self.assertEqual(decision["action"], "b")

    def test_stall_recovery_reselects_third_move_when_first_move_has_no_pp(self):
        controller = EarlyBattleController()
        stalled_state = _state(
            menu_active=False,
            text_box_active=False,
            enemy_hp=3,
            battle_type="wild",
            battle_stall_turns=18,
            moves=[
                {"move_id": 10, "pp": 0},
                {"move_id": 45, "pp": 40},
                {"move_id": 52, "pp": 25},
            ],
        )

        actions = [
            controller.maybe_decide(stalled_state, "battle")["action"]
            for _ in range(7)
        ]

        self.assertEqual(actions, ["b", "up", "left", "a", "left", "down", "a"])

    def test_stall_recovery_prefers_second_move_when_only_fallback_slot_has_pp(self):
        controller = EarlyBattleController()
        stalled_state = _state(
            menu_active=False,
            text_box_active=False,
            enemy_hp=8,
            battle_type="wild",
            battle_stall_turns=18,
            moves=[
                {"move_id": 10, "pp": 0},
                {"move_id": 33, "pp": 35},
            ],
        )

        actions = [
            controller.maybe_decide(stalled_state, "battle")["action"]
            for _ in range(7)
        ]

        self.assertEqual(actions, ["b", "up", "left", "a", "up", "right", "a"])

    def test_stall_recovery_clears_once_battle_text_returns(self):
        controller = EarlyBattleController()
        stalled_state = _state(
            menu_active=False,
            text_box_active=False,
            enemy_hp=3,
            battle_type="wild",
            battle_stall_turns=18,
            moves=[
                {"move_id": 10, "pp": 0},
                {"move_id": 45, "pp": 40},
                {"move_id": 52, "pp": 25},
            ],
        )

        first = controller.maybe_decide(stalled_state, "battle")
        resumed_text = controller.maybe_decide(
            _state(
                menu_active=False,
                text_box_active=True,
                enemy_hp=3,
                battle_type="wild",
                battle_stall_turns=0,
                moves=[
                    {"move_id": 10, "pp": 0},
                    {"move_id": 45, "pp": 40},
                    {"move_id": 52, "pp": 25},
                ],
            ),
            "battle",
        )
        restarted = controller.maybe_decide(stalled_state, "battle")

        self.assertEqual(first["action"], "b")
        self.assertEqual(resumed_text["action"], "a")
        self.assertEqual(restarted["action"], "b")

    def test_ignores_multi_mon_party_after_early_game_scope(self):
        controller = EarlyBattleController()

        decision = controller.maybe_decide(_state(party_size=2), "battle")

        self.assertIsNone(decision)

    def test_ignores_non_battle_states(self):
        controller = EarlyBattleController()

        decision = controller.maybe_decide(_state(in_battle=False), "overworld")

        self.assertIsNone(decision)


class EarlyBattleStageSpecTests(unittest.TestCase):
    def test_llm_primary_stage_list_includes_early_battle_before_cached_ai(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"decision.llm_primary_mode": True})

        stage_names = [name for name, _ in agent._get_decision_stage_specs()]

        self.assertIn("early_battle", stage_names)
        self.assertLess(stage_names.index("early_battle"), stage_names.index("cached_ai_plan"))

    def test_standard_stage_list_includes_early_battle_after_oak_lab_rival(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({})

        stage_names = [name for name, _ in agent._get_decision_stage_specs()]

        self.assertIn("early_battle", stage_names)
        self.assertLess(stage_names.index("oak_lab_rival_battle"), stage_names.index("early_battle"))
        self.assertLess(stage_names.index("early_battle"), stage_names.index("post_battle_intro_route"))

    def test_ai_full_control_llm_primary_stage_list_removes_scripted_battle_and_route_owners(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "decision.llm_primary_mode": True,
                "decision.ai_full_control_mode": True,
            }
        )

        stage_names = [name for name, _ in agent._get_decision_stage_specs()]

        self.assertNotIn("early_battle", stage_names)
        self.assertNotIn("post_battle_intro_route", stage_names)
        self.assertNotIn("viridian_parcel", stage_names)
        self.assertNotIn("post_pokedex_departure", stage_names)
        self.assertIn("cached_ai_plan", stage_names)
        self.assertIn("stable_ui_recovery", stage_names)


if __name__ == "__main__":
    unittest.main()
