import unittest

from src.control.oak_lab_starter import OakLabStarterController


def _state(x=5, y=3, direction="up"):
    return {
        "memory": {
            "position": {"map_id": 40, "x": x, "y": y},
            "direction": direction,
            "party": [],
            "in_battle": False,
        }
    }


class OakLabStarterControllerTests(unittest.TestCase):
    def test_partial_prompt_hash_queues_remaining_handoff_steps(self):
        controller = OakLabStarterController()

        first = controller.maybe_decide(
            _state(),
            "f152ef346d4d1a5414e6edb7f5e98d90",
        )
        second = controller.maybe_decide(_state(), None)
        third = controller.maybe_decide(_state(), None)

        self.assertEqual(first["action"], "a")
        self.assertEqual(second["action"], "a")
        self.assertEqual(third["action"], "down")

    def test_full_prompt_hash_goes_straight_to_down_after_one_confirm(self):
        controller = OakLabStarterController()

        first = controller.maybe_decide(
            _state(),
            "0c512922c5124e91091885e663ffb2d7",
        )
        second = controller.maybe_decide(_state(), None)

        self.assertEqual(first["action"], "a")
        self.assertEqual(second["action"], "down")

    def test_pending_macro_is_cleared_when_position_changes(self):
        controller = OakLabStarterController()
        controller.maybe_decide(
            _state(),
            "0c512922c5124e91091885e663ffb2d7",
        )

        decision = controller.maybe_decide(_state(x=5, y=4, direction="down"), None)

        self.assertIsNone(decision)


if __name__ == "__main__":
    unittest.main()
