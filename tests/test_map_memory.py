import tempfile
import unittest

from src.state.map_memory import MapMemory


class MapMemorySnapshotTests(unittest.TestCase):
    def test_snapshot_marks_player_warp_frontier_and_blocked_walls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MapMemory(save_dir=tmpdir)
            memory.update_position(1, 10, 10)
            memory.update_position(1, 11, 10, previous_position={"map_id": 1, "x": 10, "y": 10})
            memory.update_position(1, 11, 11, previous_position={"map_id": 1, "x": 11, "y": 10})
            memory.warp_points[(1, 10, 10)] = {"dest_map": 2, "dest_x": 1, "dest_y": 1, "count": 1}
            memory.record_failed_move(1, 11, 11, "right")
            memory.record_failed_move(1, 11, 11, "right")

            snapshot = memory.build_map_snapshot(1, current_position=(11, 11), padding=0, max_width=8, max_height=8)

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


if __name__ == "__main__":
    unittest.main()
