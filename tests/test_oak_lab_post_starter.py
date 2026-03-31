import unittest

from src.control.oak_lab_post_starter import OakLabPostStarterController


def _state(
    *,
    x=5,
    y=3,
    direction="right",
    badge_count=0,
    level=5,
    moves=None,
    in_battle=False,
    text_box_active=False,
    menu_active=False,
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
            "ui": {
                "text_box_active": text_box_active,
                "menu_active": menu_active,
            },
        }
    }


class OakLabPostStarterControllerTests(unittest.TestCase):
    def test_pushes_down_from_post_starter_table_when_dialogue_has_cleared(self):
        controller = OakLabPostStarterController()

        decision = controller.maybe_decide(_state(x=5, y=3), "indoor")

        self.assertEqual(decision["action"], "down")

    def test_continues_down_once_the_exit_lane_opens(self):
        controller = OakLabPostStarterController()

        decision = controller.maybe_decide(_state(x=5, y=4, direction="down"), "overworld")

        self.assertEqual(decision["action"], "down")

    def test_dialogue_turns_are_left_to_dialogue_timing(self):
        controller = OakLabPostStarterController()

        decision = controller.maybe_decide(
            _state(x=5, y=3, text_box_active=True),
            "dialogue",
        )

        self.assertIsNone(decision)

    def test_later_party_state_does_not_trigger_handoff_controller(self):
        controller = OakLabPostStarterController()

        decision = controller.maybe_decide(_state(level=6), "indoor")

        self.assertIsNone(decision)


if __name__ == "__main__":
    unittest.main()
