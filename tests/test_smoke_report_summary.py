import unittest
from pathlib import Path

from scripts.smoke_report_summary import (
    _aggregate_rows,
    _render_markdown,
    _summarize_report,
)


class SmokeReportSummaryTests(unittest.TestCase):
    def test_summarize_report_extracts_final_progress_flags(self):
        row = _summarize_report(
            Path("tmp/report_a.json"),
            {
                "requested_checkpoint": "checkpoint_1",
                "turn_delta": 900,
                "completed_requested_turns": True,
                "fatal_error": None,
                "llm_primary_mode": True,
                "ai_full_control_mode": True,
                "pure_llm_mode": False,
                "final_state": {
                    "position": {"map_id": 13, "x": 8, "y": 71},
                    "visual": {"screen_type": "overworld"},
                    "in_battle": False,
                    "party": [{"level": 9}, {"level": 7}],
                },
                "story_markers": {
                    "reached_playable": True,
                    "got_starter": True,
                    "reached_route1": True,
                    "reached_viridian_city": True,
                    "entered_viridian_mart": True,
                    "entered_oaks_lab": True,
                    "obtained_oaks_parcel": True,
                    "got_pokedex": True,
                    "delivered_oaks_parcel": True,
                    "started_post_pokedex_departure": True,
                    "reached_route2": True,
                    "reached_viridian_forest": False,
                },
                "report_validation": {
                    "timeline_turns_monotonic": True,
                    "final_state_matches_end_turn": True,
                    "timeline_last_turn_matches_end_turn": True,
                },
                "ai_control_metrics": {
                    "total_turns": 900,
                    "main_model_turns": 630,
                    "ai_plan_turns": 90,
                    "ai_authored_turns": 720,
                    "deterministic_tool_turns": 140,
                    "fallback_turns": 40,
                    "main_model_ratio": 0.7,
                    "ai_authored_ratio": 0.8,
                    "deterministic_tool_ratio": 0.1556,
                    "fallback_ratio": 0.0444,
                    "ai_dominant": True,
                },
                "decision_source_counts": {"viridian_parcel": 100},
                "decision_path_counts": {"tool": 900},
            },
        )

        self.assertEqual(row["highest_party_level"], 9)
        self.assertTrue(row["obtained_oaks_parcel"])
        self.assertTrue(row["reached_route1"])
        self.assertTrue(row["got_pokedex"])
        self.assertTrue(row["reached_route2"])
        self.assertFalse(row["reached_viridian_forest"])
        self.assertTrue(row["timeline_valid"])
        self.assertEqual(row["best_story_progress"], "reached_route2")
        self.assertEqual(row["mode"], "llm-primary+ai-full")
        self.assertEqual(row["ai_authored_turns"], 720)
        self.assertEqual(row["ai_authored_ratio"], 0.8)
        self.assertTrue(row["ai_dominant"])

    def test_aggregate_rows_counts_successes(self):
        aggregate = _aggregate_rows(
            [
                {
                    "completed_requested_turns": True,
                    "fatal_error": None,
                    "timeline_valid": True,
                    "obtained_oaks_parcel": True,
                    "delivered_oaks_parcel": True,
                    "got_pokedex": True,
                    "started_post_pokedex_departure": True,
                    "reached_route1": True,
                    "reached_route2": True,
                    "reached_viridian_forest": False,
                    "highest_party_level": 9,
                    "ai_authored_ratio": 0.8,
                    "main_model_ratio": 0.7,
                    "ai_dominant": True,
                    "ai_full_control_mode": True,
                },
                {
                    "completed_requested_turns": False,
                    "fatal_error": "boom",
                    "timeline_valid": False,
                    "obtained_oaks_parcel": False,
                    "delivered_oaks_parcel": False,
                    "got_pokedex": False,
                    "started_post_pokedex_departure": False,
                    "reached_route1": False,
                    "reached_route2": False,
                    "reached_viridian_forest": False,
                    "highest_party_level": 6,
                    "ai_authored_ratio": 0.25,
                    "main_model_ratio": 0.2,
                    "ai_dominant": False,
                    "ai_full_control_mode": False,
                },
            ]
        )

        self.assertEqual(aggregate["report_count"], 2)
        self.assertEqual(aggregate["completed_count"], 1)
        self.assertEqual(aggregate["fatal_error_count"], 1)
        self.assertEqual(aggregate["timeline_valid_count"], 1)
        self.assertEqual(aggregate["obtained_oaks_parcel_count"], 1)
        self.assertEqual(aggregate["delivered_oaks_parcel_count"], 1)
        self.assertEqual(aggregate["reached_route1_count"], 1)
        self.assertEqual(aggregate["max_party_level"], 9)
        self.assertEqual(aggregate["ai_dominant_count"], 1)
        self.assertEqual(aggregate["ai_full_control_count"], 1)
        self.assertEqual(aggregate["avg_ai_authored_ratio"], 0.525)
        self.assertEqual(aggregate["avg_main_model_ratio"], 0.45)

    def test_render_markdown_includes_key_table_values(self):
        markdown = _render_markdown(
            [
                {
                    "report_name": "report_a.json",
                    "mode": "llm-primary+ai-full",
                    "best_story_progress": "reached_route2",
                    "ai_authored_ratio": 0.8,
                    "deterministic_tool_ratio": 0.1556,
                    "turn_delta": 900,
                    "final_map": 13,
                    "final_x": 8,
                    "final_y": 71,
                    "final_screen": "overworld",
                    "got_pokedex": True,
                    "reached_route2": True,
                    "reached_viridian_forest": False,
                    "fatal_error": None,
                    "timeline_valid": True,
                }
            ],
            {
                "report_count": 1,
                "completed_count": 1,
                "fatal_error_count": 0,
                "timeline_valid_count": 1,
                "obtained_oaks_parcel_count": 1,
                "delivered_oaks_parcel_count": 1,
                "got_pokedex_count": 1,
                "started_post_pokedex_departure_count": 1,
                "reached_route1_count": 1,
                "reached_viridian_city_count": 1,
                "entered_viridian_mart_count": 1,
                "reached_route2_count": 1,
                "reached_viridian_forest_count": 0,
                "ai_dominant_count": 1,
                "ai_full_control_count": 1,
                "avg_ai_authored_ratio": 0.8,
                "avg_main_model_ratio": 0.7,
                "max_party_level": 9,
            },
        )

        self.assertIn("# Smoke Report Summary", markdown)
        self.assertIn("report_a.json", markdown)
        self.assertIn("13 (8,71)", markdown)
        self.assertIn("Reports delivering Oak's Parcel: 1", markdown)
        self.assertIn("Reports reaching Route 1: 1", markdown)
        self.assertIn("Avg AI-authored ratio: 0.8", markdown)
        self.assertIn("| report_a.json | llm-primary+ai-full | reached_route2 | 80.0% | n/a | 15.6% |", markdown)


if __name__ == "__main__":
    unittest.main()
