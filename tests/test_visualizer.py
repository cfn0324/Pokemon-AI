import unittest

import numpy as np

from src.visualization.visualizer import GameVisualizer


class VisualizerStateContractTests(unittest.TestCase):
    def _make_visualizer(self):
        visualizer = object.__new__(GameVisualizer)
        visualizer.running = False
        visualizer.current_state = {}
        return visualizer

    def test_build_dashboard_state_preserves_runtime_timestamp_and_aliases(self):
        visualizer = self._make_visualizer()

        payload = visualizer._build_dashboard_state(
            {
                "turn": 12,
                "timestamp": "2026-04-03T20:00:00",
                "memory": {
                    "position": {"map_id": 40, "x": 5, "y": 3},
                    "badge_count": 0,
                    "party": [{"species": "Charmander"}],
                    "money": 3000,
                    "in_battle": False,
                },
                "pre_world": False,
                "pre_starter_script": False,
                "phase_hint": "indoor",
                "visual": {"screen_type": "indoor"},
                "exploration": {"nearby_unexplored": [(5, 4)]},
                "map_memory": {
                    "current_map": 40,
                    "explored_tiles": 36,
                    "total_tiles": 200,
                    "exploration_percent": 18.0,
                },
                "navigation": {"frontier_count": 24},
                "deltas": {"movement_stall_turns": 1},
                "movement_pattern": {"micro_loop_warning": False},
                "battle_summary": {"phase": "not_in_battle"},
            }
        )

        self.assertEqual(payload["timestamp"], "2026-04-03T20:00:00")
        self.assertEqual(payload["screen_type"], "indoor")
        self.assertEqual(payload["exploration"]["current_map"], 40)
        self.assertEqual(payload["exploration"]["frontier_count"], 24)
        self.assertEqual(payload["map_memory"]["exploration_percent"], 18.0)
        self.assertEqual(payload["exploration"]["nearby_unexplored"], [[5, 4]])

    def test_update_state_serializes_numpy_scalars(self):
        visualizer = self._make_visualizer()

        visualizer.update_state(
            {
                "turn": np.int64(7),
                "memory": {
                    "position": {"map_id": np.int64(1), "x": np.int64(9), "y": np.int64(4)},
                    "badge_count": np.int64(1),
                    "party": [],
                    "money": np.int64(1200),
                    "in_battle": np.bool_(False),
                },
                "visual": {"screen_type": "overworld"},
                "map_memory": {"exploration_percent": np.float64(12.5)},
                "navigation": {"frontier_count": np.int64(3)},
            }
        )

        self.assertEqual(visualizer.current_state["turn"], 7)
        self.assertEqual(visualizer.current_state["position"]["map_id"], 1)
        self.assertEqual(visualizer.current_state["money"], 1200)
        self.assertEqual(visualizer.current_state["exploration"]["exploration_percent"], 12.5)
        self.assertEqual(visualizer.current_state["exploration"]["frontier_count"], 3)


if __name__ == "__main__":
    unittest.main()
