import unittest

from src.control.post_battle_intro_route import PostBattleIntroRouteController


def _state(
    *,
    map_id=40,
    x=5,
    y=6,
    level=6,
    money=3175,
    item_count=0,
    in_battle=False,
    text_box_active=False,
    events=None,
):
    return {
        "memory": {
            "position": {"map_id": map_id, "x": x, "y": y},
            "badge_count": 0,
            "money": money,
            "item_count": item_count,
            "in_battle": in_battle,
            "ui": {"text_box_active": text_box_active, "menu_active": False},
            "party": [{"level": level, "moves": [{"move_id": 10}, {"move_id": 45}]}],
            "events": dict(events or {}),
        }
    }


class PostBattleIntroRouteControllerTests(unittest.TestCase):
    def test_advances_post_battle_dialogue_without_ai(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(_state(text_box_active=True), "dialogue")

        self.assertEqual(decision["action"], "a")

    def test_stale_text_flag_in_overworld_prefers_movement(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(_state(text_box_active=True), "overworld")

        self.assertEqual(decision["action"], "down")

    def test_walks_down_out_of_oaks_lab(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(_state(), "overworld")

        self.assertEqual(decision["action"], "down")

    def test_starts_from_lower_lab_checkpoint_drift(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(_state(map_id=40, x=4, y=8), "overworld")

        self.assertEqual(decision["action"], "down")

    def test_is_guided_state_matches_early_route_start_window(self):
        controller = PostBattleIntroRouteController()

        self.assertTrue(controller.is_guided_state(_state(map_id=40, x=4, y=8)))

    def test_routes_right_around_the_lab_fence(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(_state(map_id=0, x=14, y=12), "overworld")

        self.assertEqual(decision["action"], "right")

    def test_routes_north_up_pallets_east_path(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(_state(map_id=0, x=16, y=13), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_routes_left_toward_the_route_1_opening(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(_state(map_id=0, x=16, y=2), "overworld")

        self.assertEqual(decision["action"], "left")

    def test_routes_up_through_the_route_1_grass_opening(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(_state(map_id=0, x=11, y=1), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_starts_route_1_northbound_from_checkpoint_state(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(_state(map_id=12, x=11, y=34), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_routes_left_at_route_1_hedge_row(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(_state(map_id=12, x=10, y=28), "overworld")

        self.assertEqual(decision["action"], "left")

    def test_routes_up_at_route_1_mid_right_lane(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(_state(map_id=12, x=12, y=23), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_routes_right_across_route_1_top_corridor(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(_state(map_id=12, x=12, y=14), "overworld")

        self.assertEqual(decision["action"], "right")

    def test_routes_left_into_viridian_gate_alignment(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(_state(map_id=12, x=14, y=2), "overworld")

        self.assertEqual(decision["action"], "left")

    def test_routes_up_through_viridian_south_exit(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(_state(map_id=12, x=11, y=1), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_continues_through_viridian_south_gate_after_route_1_warp(self):
        controller = PostBattleIntroRouteController()
        controller.maybe_decide(_state(map_id=12, x=11, y=34), "overworld")

        decision = controller.maybe_decide(_state(map_id=1, x=21, y=35), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_steps_left_around_viridian_south_sign(self):
        controller = PostBattleIntroRouteController()
        controller.maybe_decide(_state(map_id=12, x=11, y=34), "overworld")

        decision = controller.maybe_decide(_state(map_id=1, x=21, y=30), "overworld")

        self.assertEqual(decision["action"], "left")

    def test_aligns_with_viridian_upper_opening(self):
        controller = PostBattleIntroRouteController()
        controller.maybe_decide(_state(map_id=12, x=11, y=34), "overworld")

        decision = controller.maybe_decide(_state(map_id=1, x=20, y=28), "overworld")

        self.assertEqual(decision["action"], "left")

    def test_hands_off_after_clearing_viridian_south_opening(self):
        controller = PostBattleIntroRouteController()
        controller.maybe_decide(_state(map_id=12, x=11, y=34), "overworld")

        decision = controller.maybe_decide(_state(map_id=1, x=19, y=27), "overworld")

        self.assertIsNone(decision)

    def test_does_not_restart_after_receiving_an_item(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(
            _state(map_id=12, x=11, y=34, item_count=1),
            "overworld",
        )

        self.assertIsNone(decision)

    def test_does_not_restart_after_receiving_oaks_parcel_flag(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(
            _state(
                map_id=12,
                x=11,
                y=34,
                events={"got_oaks_parcel": True},
            ),
            "overworld",
        )

        self.assertIsNone(decision)

    def test_does_not_restart_after_getting_pokedex(self):
        controller = PostBattleIntroRouteController()

        decision = controller.maybe_decide(
            _state(
                map_id=40,
                x=5,
                y=6,
                events={"got_pokedex": True, "oak_got_parcel": True},
            ),
            "overworld",
        )

        self.assertIsNone(decision)


if __name__ == "__main__":
    unittest.main()
