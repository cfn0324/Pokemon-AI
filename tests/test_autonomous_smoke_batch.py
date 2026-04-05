import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from scripts.autonomous_smoke_batch import (
    _build_output_paths,
    _build_smoke_command,
    _environment_snapshot,
    _sanitize_label,
    _summarize_reports,
)


class AutonomousSmokeBatchTests(unittest.TestCase):
    def test_sanitize_label_rewrites_spaces_and_symbols(self):
        self.assertEqual(_sanitize_label(" phase 2 / baseline "), "phase_2_baseline")

    def test_build_output_paths_places_summary_files_under_batch_dir(self):
        root = Path("tmp/real_ai_batches").resolve()
        paths = _build_output_paths(root, "batch_a")

        self.assertEqual(paths["batch_dir"], root / "batch_a")
        self.assertEqual(paths["summary_markdown"], root / "batch_a" / "batch_a_summary.md")
        self.assertEqual(paths["summary_json"], root / "batch_a" / "batch_a_summary.json")
        self.assertEqual(paths["manifest"], root / "batch_a" / "batch_a_manifest.json")

    def test_build_smoke_command_keeps_protocol_flags(self):
        args = Namespace(
            checkpoint="checkpoint_195913",
            turns=120,
            llm_primary=True,
            pure_llm=False,
            research_mode=False,
            ai_full_control=True,
            reset_context=True,
            ai_timeout=25,
            same_turn_budget=30,
            decision_max_tokens=384,
            action_plan_max_actions=3,
        )

        command = _build_smoke_command(args, Path("tmp/report.json"))

        self.assertIn("--checkpoint", command)
        self.assertIn("checkpoint_195913", command)
        self.assertIn("--llm-primary", command)
        self.assertIn("--ai-full-control", command)
        self.assertIn("--reset-context", command)
        self.assertIn("--decision-max-tokens", command)
        self.assertIn("384", command)
        self.assertNotIn("--pure-llm", command)

    def test_environment_snapshot_never_exposes_api_key_value(self):
        snapshot = _environment_snapshot(
            {
                "AI_BASE_URL": "https://example.invalid/v1",
                "AI_MODEL": "gpt-5.4",
                "AI_API_KEY": "secret-value",
            }
        )

        self.assertEqual(snapshot["AI_BASE_URL"], "https://example.invalid/v1")
        self.assertEqual(snapshot["AI_MODEL"], "gpt-5.4")
        self.assertTrue(snapshot["AI_API_KEY_present"])
        self.assertNotIn("secret-value", json.dumps(snapshot, ensure_ascii=False))

    def test_summarize_reports_builds_aggregate_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            report_path.write_text(
                json.dumps(
                    {
                        "requested_checkpoint": "checkpoint_195913",
                        "turn_delta": 120,
                        "completed_requested_turns": True,
                        "fatal_error": None,
                        "llm_primary_mode": True,
                        "ai_full_control_mode": True,
                        "pure_llm_mode": False,
                        "final_state": {
                            "position": {"map_id": 40, "x": 4, "y": 5},
                            "visual": {"screen_type": "overworld"},
                            "in_battle": False,
                            "party": [{"level": 6}],
                        },
                        "story_markers": {
                            "obtained_oaks_parcel": True,
                            "delivered_oaks_parcel": False,
                            "got_pokedex": False,
                            "started_post_pokedex_departure": False,
                            "reached_route2": False,
                            "reached_viridian_forest": False,
                        },
                        "report_validation": {
                            "timeline_turns_monotonic": True,
                            "final_state_matches_end_turn": True,
                            "timeline_last_turn_matches_end_turn": True,
                        },
                        "ai_control_metrics": {
                            "total_turns": 120,
                            "main_model_turns": 90,
                            "ai_plan_turns": 10,
                            "ai_authored_turns": 100,
                            "deterministic_tool_turns": 15,
                            "fallback_turns": 5,
                            "main_model_ratio": 0.75,
                            "ai_authored_ratio": 0.8333,
                            "deterministic_tool_ratio": 0.125,
                            "fallback_ratio": 0.0417,
                            "ai_dominant": True,
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = _summarize_reports([report_path])

        self.assertEqual(payload["aggregate"]["report_count"], 1)
        self.assertEqual(payload["aggregate"]["obtained_oaks_parcel_count"], 1)
        self.assertEqual(payload["aggregate"]["delivered_oaks_parcel_count"], 0)
        self.assertIn("obtained_oaks_parcel", payload["markdown"])


if __name__ == "__main__":
    unittest.main()
