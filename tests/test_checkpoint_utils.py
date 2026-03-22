import json
import tempfile
import unittest
from pathlib import Path

from src.runtime.checkpoints import (
    build_checkpoint_metadata,
    list_checkpoints,
    load_checkpoint_metadata,
    prune_old_checkpoints,
    write_checkpoint_metadata,
)


class CheckpointUtilsTests(unittest.TestCase):
    def test_list_checkpoints_sorts_newest_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for turn in (12, 5, 31):
                checkpoint_dir = root / f"checkpoint_{turn}"
                checkpoint_dir.mkdir()
                write_checkpoint_metadata(
                    checkpoint_dir,
                    build_checkpoint_metadata(
                        name=checkpoint_dir.name,
                        turn=turn,
                        current_state={"memory": {"position": {"map_id": 1, "x": turn, "y": 0}}},
                    ),
                )

            checkpoints = list_checkpoints(root)
            self.assertEqual([item["turn"] for item in checkpoints], [31, 12, 5])

    def test_load_checkpoint_metadata_falls_back_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_dir = Path(tmpdir) / "checkpoint_77"
            checkpoint_dir.mkdir()

            metadata = load_checkpoint_metadata(checkpoint_dir)
            self.assertEqual(metadata["turn"], 77)
            self.assertEqual(metadata["name"], "checkpoint_77")
            self.assertIsNone(metadata["screen_type"])

    def test_prune_old_checkpoints_keeps_latest_n(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for turn in (10, 20, 30):
                checkpoint_dir = root / f"checkpoint_{turn}"
                checkpoint_dir.mkdir()
                write_checkpoint_metadata(
                    checkpoint_dir,
                    build_checkpoint_metadata(name=checkpoint_dir.name, turn=turn),
                )

            removed = prune_old_checkpoints(root, keep_latest=2)
            self.assertEqual(sorted(path.name for path in removed), ["checkpoint_10"])
            self.assertEqual(
                [item["name"] for item in list_checkpoints(root)],
                ["checkpoint_30", "checkpoint_20"],
            )


if __name__ == "__main__":
    unittest.main()
