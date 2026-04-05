import unittest

from src.control.post_pokedex_departure_controller import PostPokedexDepartureController


def _state(
    *,
    map_id=40,
    x=5,
    y=3,
    level=6,
    item_count=0,
    in_battle=False,
    text_box_active=False,
    events=None,
):
    merged_events = {"got_pokedex": True}
    merged_events.update(events or {})
    return {
        "memory": {
            "position": {"map_id": map_id, "x": x, "y": y},
            "badge_count": 0,
            "item_count": item_count,
            "in_battle": in_battle,
            "ui": {"text_box_active": text_box_active, "menu_active": False},
            "party": [{"level": level}],
            "events": merged_events,
        }
    }


class PostPokedexDepartureControllerTests(unittest.TestCase):
    def test_advances_lingering_pokedex_dialogue(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(
            _state(text_box_active=True),
            "dialogue",
        )

        self.assertEqual(decision["action"], "a")

    def test_route2_stale_battle_flag_still_prefers_movement(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(
            _state(map_id=13, x=8, y=71, text_box_active=True),
            "battle",
        )

        self.assertEqual(decision["action"], "up")

    def test_steps_left_off_oaks_counter_lane_before_departure(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=40, x=5, y=3), "indoor")

        self.assertEqual(decision["action"], "left")

    def test_walks_down_oaks_lab_aisle(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=40, x=4, y=8), "indoor")

        self.assertEqual(decision["action"], "down")

    def test_steps_through_oaks_lab_exit_warp(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=40, x=4, y=11), "indoor")

        self.assertEqual(decision["action"], "down")

    def test_routes_around_pallet_lab_fence_to_east_path(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=0, x=12, y=12), "overworld")

        self.assertEqual(decision["action"], "right")

    def test_heads_north_up_pallets_east_lane(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=0, x=16, y=8), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_recovers_from_players_house_doorstep_after_blackout(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=0, x=5, y=6), "indoor")

        self.assertEqual(decision["action"], "down")

    def test_recovers_from_players_house_side_lane_after_blackout(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=0, x=5, y=8), "overworld")

        self.assertEqual(decision["action"], "right")

    def test_climbs_home_recovery_lane_back_toward_route1(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=0, x=8, y=6), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_lines_up_with_pallets_north_exit(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=0, x=16, y=2), "overworld")

        self.assertEqual(decision["action"], "left")

    def test_blackout_recovery_keeps_sliding_right_until_pallet_exit_is_aligned(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=0, x=9, y=2), "overworld")

        self.assertEqual(decision["action"], "right")

    def test_starts_route1_northbound(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=12, x=11, y=34), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_clears_viridian_south_sign_alignment(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=1, x=21, y=30), "overworld")

        self.assertEqual(decision["action"], "left")

    def test_continues_north_through_viridian_main_road(self):
        controller = PostPokedexDepartureController()
        controller.maybe_decide(_state(map_id=12, x=11, y=34), "overworld")

        decision = controller.maybe_decide(_state(map_id=1, x=19, y=27), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_sidesteps_viridian_north_sign_before_exiting(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=1, x=19, y=2), "overworld")

        self.assertEqual(decision["action"], "left")

    def test_climbs_route2_south_corridor(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=13, x=8, y=71), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_turns_left_at_route2_top_junction(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=13, x=8, y=62), "overworld")

        self.assertEqual(decision["action"], "left")

    def test_recovers_right_from_route2s_west_dead_end(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=13, x=3, y=62), "overworld")

        self.assertEqual(decision["action"], "right")

    def test_climbs_route2s_inner_northbound_lane(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=13, x=7, y=60), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_turns_west_through_route2s_mid_lane_opening(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=13, x=6, y=57), "overworld")

        self.assertEqual(decision["action"], "left")

    def test_steps_into_route2s_upper_west_corridor(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=13, x=5, y=57), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_climbs_route2s_upper_west_corridor(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=13, x=4, y=54), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_crosses_route2s_upper_connector(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=13, x=5, y=48), "overworld")

        self.assertEqual(decision["action"], "right")

    def test_climbs_route2s_final_gate_column(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=13, x=9, y=46), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_lines_up_with_route2s_forest_gate_entrance(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=13, x=5, y=44), "overworld")

        self.assertEqual(decision["action"], "left")

    def test_steps_into_route2s_forest_gate_from_runtime_entrance_tile(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=13, x=3, y=44), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_steps_into_route2s_forest_gate_from_warp_coordinate(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=13, x=3, y=43), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_crosses_viridian_forest_south_gate_interior(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=50, x=4, y=7), "indoor")

        self.assertEqual(decision["action"], "up")

    def test_sidesteps_onto_viridian_forest_south_gates_live_exit_tile(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=50, x=4, y=1), "indoor")

        self.assertEqual(decision["action"], "right")

    def test_steps_out_of_viridian_forest_south_gate_after_top_sidestep(self):
        controller = PostPokedexDepartureController()

        decision = controller.maybe_decide(_state(map_id=50, x=5, y=1), "indoor")

        self.assertEqual(decision["action"], "up")

    def test_hands_off_after_reaching_viridian_forest(self):
        controller = PostPokedexDepartureController()
        controller.maybe_decide(_state(map_id=50, x=4, y=7), "indoor")

        decision = controller.maybe_decide(_state(map_id=51, x=16, y=47), "overworld")

        self.assertIsNone(decision)
        self.assertFalse(controller.is_guided_state(_state(map_id=51, x=16, y=47)))

    def test_can_resume_after_forest_blackout_returns_home(self):
        controller = PostPokedexDepartureController()
        controller.maybe_decide(_state(map_id=13, x=8, y=71), "overworld")
        controller.maybe_decide(_state(map_id=51, x=16, y=47), "overworld")

        decision = controller.maybe_decide(_state(map_id=0, x=5, y=6), "indoor")

        self.assertEqual(decision["action"], "down")
        self.assertTrue(controller.is_guided_state(_state(map_id=0, x=5, y=6)))

    def test_is_guided_state_matches_post_pokedex_lab_window(self):
        controller = PostPokedexDepartureController()

        self.assertTrue(controller.is_guided_state(_state(map_id=40, x=5, y=3)))

    def test_is_guided_state_owns_viridian_northbound_segment(self):
        controller = PostPokedexDepartureController()

        self.assertTrue(controller.is_guided_state(_state(map_id=1, x=19, y=17)))

    def test_is_guided_state_owns_route2_south_segment(self):
        controller = PostPokedexDepartureController()

        self.assertTrue(controller.is_guided_state(_state(map_id=13, x=8, y=66)))

    def test_is_guided_state_owns_forest_south_gate(self):
        controller = PostPokedexDepartureController()

        self.assertTrue(controller.is_guided_state(_state(map_id=50, x=4, y=4)))

    def test_is_guided_state_drops_once_scope_no_longer_matches(self):
        controller = PostPokedexDepartureController()

        self.assertFalse(
            controller.is_guided_state(
                _state(
                    map_id=40,
                    x=8,
                    y=11,
                    events={"got_pokedex": True, "oak_got_parcel": True},
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
