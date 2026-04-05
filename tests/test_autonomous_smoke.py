import unittest
from types import SimpleNamespace

from scripts.autonomous_smoke import (
    _build_report_validation,
    _build_timeline,
    _derive_story_markers,
    _simplify_state,
    _summarize_ai_control,
)


class AutonomousSmokeTimelineTests(unittest.TestCase):
    def test_simplify_state_keeps_events_item_count_and_ui(self):
        state = {
            "turn": 88,
            "memory": {
                "position": {"map_id": 40, "x": 5, "y": 3},
                "badge_count": 0,
                "money": 1587,
                "item_count": 1,
                "party": [{"level": 7}],
                "in_battle": False,
                "events": {"got_oaks_parcel": True},
                "ui": {"text_box_active": True, "menu_active": False},
            },
            "visual": {"screen_type": "dialogue"},
        }

        simplified = _simplify_state(state)

        self.assertEqual(simplified["turn"], 88)
        self.assertEqual(simplified["item_count"], 1)
        self.assertTrue(simplified["events"]["got_oaks_parcel"])
        self.assertTrue(simplified["ui"]["text_box_active"])

    def test_build_timeline_prefers_turn_screen_type(self):
        turn = SimpleNamespace(
            turn_number=42,
            action="start",
            screen_type="startup_menu",
            reasoning="Menu is visible, confirm New Game.",
            result="ok",
            decision_source="ai",
            decision_path="ai",
            state={
                "visual": {
                    "screen_type": "unknown",
                    "ram_screen_type": "title",
                },
                "memory": {
                    "position": {"map_id": 1, "x": 2, "y": 3},
                    "party": [],
                },
            },
        )
        agent = SimpleNamespace(
            main_agent=SimpleNamespace(
                context=SimpleNamespace(recent_turns=[turn])
            )
        )

        timeline = _build_timeline(agent, start_turn=40)

        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["screen_type"], "startup_menu")
        self.assertEqual(timeline[0]["observed_screen_type"], "unknown")
        self.assertIsNone(timeline[0]["model_latency_seconds"])
        self.assertIsNone(timeline[0]["model_request_count"])

    def test_build_timeline_accepts_explicit_record_list(self):
        turns = [
            {
                "turn_number": 50,
                "action": "left",
                "reasoning": "probe left",
                "result": "After left: position did not change",
                "decision_source": "cached_ai_plan",
                "decision_path": "tool",
                "state": {
                    "visual": {"screen_type": "overworld"},
                    "memory": {
                        "position": {"map_id": 0, "x": 10, "y": 9},
                        "party": ["Charmander"],
                    },
                },
            }
        ]
        agent = SimpleNamespace(main_agent=SimpleNamespace(context=SimpleNamespace(recent_turns=[])))

        timeline = _build_timeline(agent, start_turn=40, turns=turns)

        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["decision_source"], "cached_ai_plan")
        self.assertEqual(timeline[0]["party_size"], 1)

    def test_derive_story_markers_reads_flags_and_map_progress(self):
        final_state = {
            "party_size": 1,
            "party": [{"level": 9}],
            "item_count": 0,
            "events": {
                "got_oaks_parcel": True,
                "oak_got_parcel": True,
                "got_pokedex": True,
            },
            "position": {"map_id": 13, "x": 8, "y": 71},
            "pre_world": False,
            "pre_starter_script": False,
        }
        timeline = [
            {"turn": 10, "decision_source": "viridian_parcel", "position": {"map_id": 1, "x": 19, "y": 20}},
            {"turn": 20, "decision_source": "viridian_parcel", "position": {"map_id": 42, "x": 3, "y": 5}},
            {"turn": 25, "decision_source": "viridian_parcel", "position": {"map_id": 12, "x": 8, "y": 9}},
            {"turn": 30, "decision_source": "post_pokedex_departure", "position": {"map_id": 13, "x": 8, "y": 71}},
            {"turn": 40, "decision_source": "post_pokedex_departure", "position": {"map_id": 50, "x": 4, "y": 7}},
            {"turn": 50, "decision_source": "post_pokedex_departure", "position": {"map_id": 51, "x": 16, "y": 47}},
        ]

        markers = _derive_story_markers(final_state, timeline)

        self.assertTrue(markers["entered_viridian_mart"])
        self.assertTrue(markers["reached_route1"])
        self.assertTrue(markers["delivered_oaks_parcel"])
        self.assertTrue(markers["got_pokedex"])
        self.assertTrue(markers["started_post_pokedex_departure"])
        self.assertTrue(markers["reached_viridian_forest"])
        self.assertEqual(markers["highest_party_level"], 9)

    def test_build_report_validation_checks_turn_alignment(self):
        final_state = {"turn": 120}
        timeline = [
            {"turn": 111},
            {"turn": 112},
            {"turn": 120},
        ]

        validation = _build_report_validation(final_state, timeline, end_turn=120)

        self.assertEqual(validation["timeline_first_turn"], 111)
        self.assertEqual(validation["timeline_last_turn"], 120)
        self.assertTrue(validation["timeline_turns_monotonic"])
        self.assertTrue(validation["final_state_matches_end_turn"])
        self.assertTrue(validation["timeline_last_turn_matches_end_turn"])

    def test_summarize_ai_control_distinguishes_ai_tool_and_fallback_turns(self):
        metrics = _summarize_ai_control(
            [
                {"decision_source": "ai", "decision_path": "ai"},
                {"decision_source": "cached_ai_plan", "decision_path": "tool"},
                {"decision_source": "guided_navigation_escape", "decision_path": "tool"},
                {"decision_source": "api_unavailable_battle_fallback", "decision_path": "fallback"},
            ]
        )

        self.assertEqual(metrics["total_turns"], 4)
        self.assertEqual(metrics["main_model_turns"], 1)
        self.assertEqual(metrics["ai_plan_turns"], 1)
        self.assertEqual(metrics["ai_authored_turns"], 2)
        self.assertEqual(metrics["deterministic_tool_turns"], 1)
        self.assertEqual(metrics["fallback_turns"], 1)
        self.assertEqual(metrics["ai_authored_ratio"], 0.5)
        self.assertTrue(metrics["ai_dominant"])


if __name__ == "__main__":
    unittest.main()
