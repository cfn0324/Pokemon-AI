import unittest

from src.control.oak_lab_starter import OakLabStarterController


def _state(
    x=5,
    y=3,
    direction="up",
    *,
    text_box_active=False,
    party=None,
    in_battle=False,
):
    return {
        "memory": {
            "position": {"map_id": 40, "x": x, "y": y},
            "direction": direction,
            "party": party or [],
            "in_battle": in_battle,
            "ui": {"text_box_active": text_box_active, "menu_active": False},
        }
    }


class OakLabStarterControllerTests(unittest.TestCase):
    def test_initial_table_alignment_starts_dialogue(self):
        controller = OakLabStarterController()

        decision = controller.maybe_decide(
            _state(),
            "506ea3b0c34b01a6a4e8a727fd3616cd",
            "dialogue",
        )

        self.assertEqual(decision["action"], "a")

    def test_table_clear_frame_turns_right_immediately(self):
        controller = OakLabStarterController()

        decision = controller.maybe_decide(
            _state(text_box_active=True),
            "b141e2771ba1c9b2e7de784d6310e24f",
            "indoor",
        )

        self.assertEqual(decision["action"], "right")

    def test_any_indoor_table_frame_turns_right_once_dialogue_is_clear(self):
        controller = OakLabStarterController()

        decision = controller.maybe_decide(
            _state(text_box_active=False),
            "unexpected_indoor_hash",
            "indoor",
        )

        self.assertEqual(decision["action"], "right")

    def test_right_facing_branch_keeps_pressing_a_even_when_screen_looks_clear(self):
        controller = OakLabStarterController()

        decision = controller.maybe_decide(
            _state(direction="right", text_box_active=False),
            "e2d871d5cf75a838300f23a0d8c0ebad",
            "indoor",
        )

        self.assertEqual(decision["action"], "a")

    def test_right_branch_realigns_if_facing_changes(self):
        controller = OakLabStarterController()
        controller.maybe_decide(
            _state(text_box_active=True),
            "b141e2771ba1c9b2e7de784d6310e24f",
            "indoor",
        )

        decision = controller.maybe_decide(
            _state(direction="down", text_box_active=False),
            "e2d871d5cf75a838300f23a0d8c0ebad",
            "indoor",
        )

        self.assertEqual(decision["action"], "right")

    def test_right_branch_realigns_if_still_facing_up(self):
        controller = OakLabStarterController()
        controller.maybe_decide(
            _state(text_box_active=False),
            "unexpected_indoor_hash",
            "indoor",
        )

        decision = controller.maybe_decide(
            _state(direction="up", text_box_active=False),
            "still_not_facing_right",
            "dialogue",
        )

        self.assertEqual(decision["action"], "right")

    def test_controller_stops_after_first_pokemon_is_obtained(self):
        controller = OakLabStarterController()

        decision = controller.maybe_decide(
            _state(party=[{"level": 5}]),
            "b6abc11683d9843a7448c85239ae7df6",
            "dialogue",
        )

        self.assertIsNone(decision)


if __name__ == "__main__":
    unittest.main()
