import unittest

from src.control.oak_lab_rival_battle import OakLabRivalBattleController


def _state(
    *,
    x=5,
    y=5,
    direction="up",
    in_battle=False,
    badge_count=0,
    level=5,
    moves=None,
    enemy_hp=20,
    menu_active=False,
    text_box_active=False,
):
    if moves is None:
        moves = [{"move_id": 10}, {"move_id": 45}]

    return {
        "memory": {
            "position": {"map_id": 40, "x": x, "y": y},
            "direction": direction,
            "badge_count": badge_count,
            "party": [
                {
                    "level": level,
                    "moves": list(moves),
                }
            ],
            "in_battle": in_battle,
            "battle": {
                "enemy_current_hp": enemy_hp,
            },
            "ui": {
                "menu_active": menu_active,
                "text_box_active": text_box_active,
            },
        }
    }


class OakLabRivalBattleControllerTests(unittest.TestCase):
    def test_steps_down_to_trigger_rival_sequence(self):
        controller = OakLabRivalBattleController()

        decision = controller.maybe_decide(_state(), "overworld")

        self.assertEqual(decision["action"], "down")

    def test_presses_a_during_prebattle_dialogue_alignment(self):
        controller = OakLabRivalBattleController()
        controller.maybe_decide(_state(), "overworld")

        decision = controller.maybe_decide(_state(x=5, y=6), "dialogue")

        self.assertEqual(decision["action"], "a")

    def test_restored_mid_battle_confirms_default_action(self):
        controller = OakLabRivalBattleController()

        decision = controller.maybe_decide(_state(x=5, y=6, in_battle=True), "battle")

        self.assertEqual(decision["action"], "a")

    def test_active_sequence_continues_after_level_up(self):
        controller = OakLabRivalBattleController()
        controller.maybe_decide(_state(), "overworld")

        decision = controller.maybe_decide(_state(x=5, y=6, in_battle=True, level=6), "battle")

        self.assertEqual(decision["action"], "a")

    def test_post_faint_battle_menu_is_closed_with_b(self):
        controller = OakLabRivalBattleController()
        controller.maybe_decide(_state(), "overworld")

        decision = controller.maybe_decide(
            _state(
                x=5,
                y=6,
                in_battle=True,
                level=6,
                enemy_hp=0,
                menu_active=True,
                text_box_active=True,
            ),
            "battle",
        )

        self.assertEqual(decision["action"], "b")

    def test_controller_stops_after_battle_has_finished(self):
        controller = OakLabRivalBattleController()
        controller.maybe_decide(_state(), "overworld")
        controller.maybe_decide(_state(x=5, y=6, in_battle=True), "battle")

        decision = controller.maybe_decide(_state(x=5, y=6, in_battle=False), "overworld")

        self.assertIsNone(decision)

    def test_later_party_state_does_not_trigger_opening_controller(self):
        controller = OakLabRivalBattleController()

        decision = controller.maybe_decide(_state(level=6), "overworld")

        self.assertIsNone(decision)


if __name__ == "__main__":
    unittest.main()
