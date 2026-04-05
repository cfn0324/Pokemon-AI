import unittest

from main import PokemonAIAgent
from src.control.viridian_parcel_controller import ViridianParcelController


class _ConfigStub:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)


def _state(
    *,
    map_id=1,
    x=19,
    y=27,
    level=7,
    item_count=0,
    in_battle=False,
    text_box_active=False,
    events=None,
):
    return {
        "memory": {
            "position": {"map_id": map_id, "x": x, "y": y},
            "badge_count": 0,
            "item_count": item_count,
            "in_battle": in_battle,
            "ui": {"text_box_active": text_box_active, "menu_active": False},
            "party": [{"level": level}],
            "events": dict(events or {}),
        }
    }


class ViridianParcelControllerTests(unittest.TestCase):
    def test_routes_up_from_viridian_main_path(self):
        controller = ViridianParcelController()

        decision = controller.maybe_decide(_state(x=19, y=23), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_turns_right_along_mart_corridor(self):
        controller = ViridianParcelController()

        decision = controller.maybe_decide(_state(x=24, y=16), "overworld")

        self.assertEqual(decision["action"], "right")

    def test_bends_down_at_blocked_east_hedge(self):
        controller = ViridianParcelController()

        decision = controller.maybe_decide(_state(x=27, y=16), "overworld")

        self.assertEqual(decision["action"], "down")

    def test_turns_right_on_lower_east_lane_before_mart(self):
        controller = ViridianParcelController()

        decision = controller.maybe_decide(_state(x=28, y=20), "overworld")

        self.assertEqual(decision["action"], "right")

    def test_steps_up_onto_mart_doorway_tile(self):
        controller = ViridianParcelController()

        decision = controller.maybe_decide(_state(x=29, y=20), "overworld")

        self.assertEqual(decision["action"], "up")

    def test_advances_mart_dialogue(self):
        controller = ViridianParcelController()

        decision = controller.maybe_decide(
            _state(map_id=42, x=3, y=5, text_box_active=True),
            "dialogue",
        )

        self.assertEqual(decision["action"], "a")

    def test_waits_for_mart_script_to_start_before_parcel(self):
        controller = ViridianParcelController()

        decision = controller.maybe_decide(
            _state(map_id=42, x=4, y=7, item_count=0),
            "indoor",
        )

        self.assertEqual(decision["action"], "wait")
        self.assertTrue(decision["allow_wait"])

    def test_exits_mart_after_receiving_parcel(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(map_id=42, x=4, y=7, item_count=0), "indoor")

        decision = controller.maybe_decide(
            _state(map_id=42, x=3, y=5, item_count=1),
            "indoor",
        )

        self.assertEqual(decision["action"], "down")

    def test_routes_back_toward_viridian_south_exit_after_parcel(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(x=25, y=20, item_count=1),
            "overworld",
        )

        self.assertEqual(decision["action"], "left")

    def test_descends_central_road_after_parcel(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(x=19, y=24, item_count=1),
            "overworld",
        )

        self.assertEqual(decision["action"], "down")

    def test_realigns_with_south_gate_opening_after_parcel(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(x=19, y=28, item_count=1),
            "overworld",
        )

        self.assertEqual(decision["action"], "right")

    def test_heads_down_final_south_exit_lane_after_parcel(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(x=21, y=34, item_count=1),
            "overworld",
        )

        self.assertEqual(decision["action"], "down")

    def test_routes_route1_return_lane_after_parcel(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(map_id=12, x=11, y=3, item_count=1),
            "overworld",
        )

        self.assertEqual(decision["action"], "right")

    def test_routes_pallet_return_back_to_lab(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(map_id=0, x=16, y=8, item_count=1),
            "overworld",
        )

        self.assertEqual(decision["action"], "down")

    def test_recovers_from_players_house_doorstep_after_blackout_with_parcel(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(map_id=0, x=5, y=6, item_count=1),
            "indoor",
        )

        self.assertEqual(decision["action"], "down")

    def test_recovers_from_players_house_side_lane_after_blackout_with_parcel(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(map_id=0, x=5, y=8, item_count=1),
            "overworld",
        )

        self.assertEqual(decision["action"], "right")

    def test_brings_blackout_recovery_lane_south_toward_oaks_lab(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(map_id=0, x=8, y=6, item_count=1),
            "overworld",
        )

        self.assertEqual(decision["action"], "down")

    def test_crosses_south_lane_from_blackout_recovery_path_to_lab_door(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(map_id=0, x=10, y=12, item_count=1),
            "overworld",
        )

        self.assertEqual(decision["action"], "right")

    def test_reenters_oaks_lab_with_parcel(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(map_id=0, x=12, y=12, item_count=1),
            "overworld",
        )

        self.assertEqual(decision["action"], "up")

    def test_walks_up_oaks_lab_aisle_to_oak(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(map_id=40, x=5, y=6, item_count=1),
            "indoor",
        )

        self.assertEqual(decision["action"], "up")

    def test_talks_to_oak_when_back_at_lab_counter(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(map_id=40, x=5, y=3, item_count=1),
            "indoor",
        )

        self.assertEqual(decision["action"], "a")

    def test_keeps_advancing_oak_scene_after_parcel_leaves_bag(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(
                map_id=40,
                x=5,
                y=3,
                item_count=0,
                events={"got_oaks_parcel": True},
            ),
            "indoor",
        )

        self.assertEqual(decision["action"], "a")

    def test_deactivates_once_pokedex_scene_flags_are_set(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(
                map_id=40,
                x=5,
                y=3,
                item_count=0,
                events={"got_pokedex": True, "oak_got_parcel": True},
            ),
            "indoor",
        )

        self.assertIsNone(decision)

    def test_is_guided_state_covers_return_trip_after_receiving_parcel(self):
        controller = ViridianParcelController()

        self.assertTrue(
            controller.is_guided_state(
                _state(
                    map_id=0,
                    x=16,
                    y=8,
                    item_count=1,
                )
            )
        )

    def test_routes_west_side_top_road_back_to_safe_oaks_lab_column(self):
        controller = ViridianParcelController()
        controller.maybe_decide(_state(x=24, y=16), "overworld")

        decision = controller.maybe_decide(
            _state(map_id=0, x=3, y=2, item_count=1),
            "overworld",
        )

        self.assertEqual(decision["action"], "right")

    def test_is_guided_state_drops_after_pokedex_scene_flags(self):
        controller = ViridianParcelController()

        self.assertFalse(
            controller.is_guided_state(
                _state(
                    map_id=40,
                    x=5,
                    y=3,
                    item_count=0,
                    events={"got_pokedex": True, "oak_got_parcel": True},
                )
            )
        )


class ViridianParcelStageSpecTests(unittest.TestCase):
    def test_llm_primary_stage_list_includes_viridian_parcel_before_cached_ai(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"decision.llm_primary_mode": True})

        stage_names = [name for name, _ in agent._get_decision_stage_specs()]

        self.assertIn("viridian_parcel", stage_names)
        self.assertLess(stage_names.index("viridian_parcel"), stage_names.index("cached_ai_plan"))

    def test_standard_stage_list_places_viridian_parcel_after_intro_route(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({})

        stage_names = [name for name, _ in agent._get_decision_stage_specs()]

        self.assertIn("viridian_parcel", stage_names)
        self.assertLess(stage_names.index("post_battle_intro_route"), stage_names.index("viridian_parcel"))


if __name__ == "__main__":
    unittest.main()
