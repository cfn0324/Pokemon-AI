import shutil
import unittest
import uuid
from pathlib import Path

from src.state.map_memory import MapMemory


class MapMemorySnapshotTests(unittest.TestCase):
    def test_snapshot_marks_player_warp_frontier_and_blocked_walls(self):
        tmpdir = Path("tmp") / f"map_memory_{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=False)
        try:
            memory = MapMemory(save_dir=tmpdir)
            memory.update_position(1, 10, 10)
            memory.update_position(1, 11, 10, previous_position={"map_id": 1, "x": 10, "y": 10})
            memory.update_position(1, 11, 11, previous_position={"map_id": 1, "x": 11, "y": 10})
            memory.warp_points[(1, 10, 10)] = {"dest_map": 2, "dest_x": 1, "dest_y": 1, "count": 1}
            memory.record_failed_move(1, 11, 11, "right")
            memory.record_failed_move(1, 11, 11, "right")

            snapshot = memory.build_map_snapshot(1, current_position=(11, 11), padding=0, max_width=8, max_height=8)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertTrue(snapshot["available"])
        rows = snapshot["rows"]
        rendered = "\n".join(rows)
        self.assertIn("P", rendered)
        self.assertIn("W", rendered)
        self.assertIn("F", rendered)
        self.assertIn("#", rendered)
        self.assertEqual(snapshot["player"], {"x": 11, "y": 11})
        self.assertEqual(snapshot["prompt_rows"], [row.replace(" ", "?") for row in rows])
        self.assertEqual(snapshot["blocked_count"], 1)
        self.assertGreaterEqual(snapshot["frontier_count"], 1)

    def test_frontier_scoring_prefers_lower_pressure_more_novel_targets(self):
        tmpdir = Path("tmp") / f"map_memory_{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=False)
        try:
            memory = MapMemory(save_dir=tmpdir)
            explored = {(x, y) for x in range(3) for y in range(3)}
            explored.update({(3, 1), (4, 1), (5, 1)})
            memory.explored_tiles[1] = explored
            for pos in explored:
                memory.visit_counts[1][pos] = 10 if pos[0] <= 2 else 1

            frontiers = memory.get_frontier_tiles(1, current_position=(2, 1))
            advice = memory.get_navigation_advice(1, 2, 1)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertEqual(frontiers[0]["position"], (5, 1))
        self.assertEqual(frontiers[0]["novelty_label"], "high")
        self.assertGreater(frontiers[0]["priority_score"], frontiers[-1]["priority_score"])
        self.assertEqual(tuple(advice["frontier_candidates"][0]["target"]), (5, 1))
        self.assertIn("local_visit_pressure", advice["frontier_candidates"][0])
        self.assertIn("global_novelty_distance", advice["frontier_candidates"][0])


if __name__ == "__main__":
    unittest.main()
