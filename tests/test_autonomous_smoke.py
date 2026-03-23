import unittest
from types import SimpleNamespace

from scripts.autonomous_smoke import _build_timeline


class AutonomousSmokeTimelineTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
