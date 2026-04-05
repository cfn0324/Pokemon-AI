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

    def test_navigation_advice_describes_adjacent_tiles(self):
        tmpdir = Path("tmp") / f"map_memory_{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=False)
        try:
            memory = MapMemory(save_dir=tmpdir)
            memory.update_position(1, 10, 10)
            memory.update_position(
                1,
                10,
                9,
                previous_position={"map_id": 1, "x": 10, "y": 10},
            )
            memory.update_position(
                1,
                10,
                10,
                previous_position={"map_id": 1, "x": 10, "y": 9},
            )
            memory.record_failed_move(1, 10, 10, "right")
            memory.record_failed_move(1, 10, 10, "right")

            advice = memory.get_navigation_advice(1, 10, 10)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        adjacent = advice["adjacent_tiles"]
        self.assertEqual(adjacent["up"]["status"], "known_exit")
        self.assertEqual(adjacent["up"]["target"], {"x": 10, "y": 9})
        self.assertEqual(adjacent["right"]["status"], "confirmed_blocked")
        self.assertEqual(adjacent["right"]["blocked_attempts"], 2)
        self.assertIn("solid blocker", adjacent["right"]["summary"])
        self.assertEqual(adjacent["left"]["status"], "frontier")
        self.assertTrue(adjacent["left"]["is_frontier_direction"])

    def test_navigation_advice_adds_warp_and_frontier_cautions(self):
        tmpdir = Path("tmp") / f"map_memory_{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=False)
        try:
            memory = MapMemory(save_dir=tmpdir)
            memory.explored_tiles[0] = {(12, 11), (12, 12), (4, 11)}
            memory.visit_counts[0][(12, 11)] = 3
            memory.visit_counts[0][(12, 12)] = 4
            memory.visit_counts[0][(11, 11)] = 2
            memory.visit_counts[0][(13, 11)] = 2
            memory.visit_counts[0][(4, 11)] = 1
            memory.warp_points[(0, 12, 12)] = {
                "dest_map": 40,
                "dest_x": 4,
                "dest_y": 11,
                "count": 1,
                "trigger_action": "right",
            }

            advice = memory.get_navigation_advice(0, 12, 11)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertEqual(advice["warp_cautions"][0]["direction"], "down")
        self.assertEqual(
            advice["warp_cautions"][0]["destination"],
            {"map_id": 40, "x": 4, "y": 11},
        )
        self.assertTrue(advice["frontier_guidance"]["current_tile_is_frontier"])
        self.assertTrue(advice["frontier_guidance"]["prefer_leave_current_frontier"])
        self.assertEqual(advice["frontier_guidance"]["recommended_direction"], "left")
        self.assertEqual(advice["frontier_guidance"]["escape_direction"], "left")
        self.assertIn(
            "stronger frontier",
            advice["frontier_guidance"]["summary"],
        )

    def test_navigation_advice_marks_current_tile_warp_source_and_trigger_action(self):
        tmpdir = Path("tmp") / f"map_memory_{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=False)
        try:
            memory = MapMemory(save_dir=tmpdir)
            memory.explored_tiles[0] = {(12, 12), (11, 12), (10, 12), (9, 11)}
            memory.visit_counts[0][(12, 12)] = 4
            memory.visit_counts[0][(11, 12)] = 2
            memory.visit_counts[0][(10, 12)] = 1
            memory.visit_counts[0][(9, 11)] = 1
            memory.warp_points[(0, 12, 12)] = {
                "dest_map": 40,
                "dest_x": 12,
                "dest_y": 11,
                "count": 2,
                "trigger_action": "right",
            }

            advice = memory.get_navigation_advice(0, 12, 12)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertEqual(
            advice["current_tile_warp"]["destination"],
            {"map_id": 40, "x": 12, "y": 11},
        )
        self.assertEqual(advice["current_tile_warp"]["trigger_action"], "right")
        self.assertEqual(advice["adjacent_tiles"]["right"]["status"], "warp_trigger")
        self.assertTrue(advice["adjacent_tiles"]["right"]["step_triggers_warp"])
        self.assertIn(
            "map transition",
            advice["adjacent_tiles"]["right"]["summary"],
        )

    def test_navigation_advice_infers_remaining_warp_trigger_direction(self):
        tmpdir = Path("tmp") / f"map_memory_{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=False)
        try:
            memory = MapMemory(save_dir=tmpdir)
            memory.explored_tiles[0] = {(12, 12), (11, 12)}
            memory.visit_counts[0][(12, 12)] = 4
            memory.visit_counts[0][(11, 12)] = 1
            memory.record_failed_move(0, 12, 12, "up")
            memory.record_failed_move(0, 12, 12, "left")
            memory.record_failed_move(0, 12, 12, "down")
            memory.warp_points[(0, 12, 12)] = {
                "dest_map": 40,
                "dest_x": 12,
                "dest_y": 11,
                "count": 2,
            }

            advice = memory.get_navigation_advice(0, 12, 12)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertEqual(advice["current_tile_warp"]["trigger_action"], "right")
        self.assertEqual(advice["current_tile_warp"]["trigger_action_source"], "inferred")
        self.assertEqual(advice["adjacent_tiles"]["right"]["status"], "warp_trigger")


if __name__ == "__main__":
    unittest.main()
