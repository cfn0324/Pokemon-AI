import unittest

from src.control.oak_lab_pre_starter import OakLabPreStarterController


def _state(
    x,
    y,
    direction="up",
    party=None,
    in_battle=False,
):
    return {
        "memory": {
            "position": {"map_id": 40, "x": x, "y": y},
            "direction": direction,
            "party": party or [],
            "in_battle": in_battle,
        }
    }


class OakLabPreStarterControllerTests(unittest.TestCase):
    def test_routes_checkpoint_start_toward_lower_corridor(self):
        controller = OakLabPreStarterController()

        decision = controller.maybe_decide(
            _state(0, 2),
            "indoor",
            None,
        )

        self.assertEqual(decision["action"], "down")

    def test_routes_lower_corridor_toward_starter_table(self):
        controller = OakLabPreStarterController()

        decision = controller.maybe_decide(
            _state(4, 5, direction="right"),
            "indoor",
            None,
        )

        self.assertEqual(decision["action"], "right")

    def test_presses_a_to_start_dialogue_at_starter_table(self):
        controller = OakLabPreStarterController()

        decision = controller.maybe_decide(
            _state(5, 3),
            "indoor",
            "b141e2771ba1c9b2e7de784d6310e24f",
        )

        self.assertEqual(decision["action"], "a")

    def test_defers_known_final_prompt_hash_to_handoff_controller(self):
        controller = OakLabPreStarterController()

        decision = controller.maybe_decide(
            _state(5, 3),
            "dialogue",
            "0c512922c5124e91091885e663ffb2d7",
        )

        self.assertIsNone(decision)

    def test_advances_dialogue_in_lower_trigger_zone(self):
        controller = OakLabPreStarterController()

        decision = controller.maybe_decide(
            _state(5, 6, direction="down"),
            "dialogue",
            "ffd8b5938598af6deace4249d6c7e99d",
        )

        self.assertEqual(decision["action"], "a")


if __name__ == "__main__":
    unittest.main()
