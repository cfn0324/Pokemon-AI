import json
import shutil
import unittest
import uuid
from pathlib import Path

from src.runtime.checkpoints import (
    build_checkpoint_metadata,
    list_checkpoints,
    list_startup_checkpoints,
    load_checkpoint_metadata,
    prune_old_checkpoints,
    write_checkpoint_metadata,
)


class CheckpointUtilsTests(unittest.TestCase):
    def test_list_checkpoints_sorts_newest_first(self):
        tmpdir = Path("tmp") / f"checkpoint_utils_{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=False)
        try:
            root = tmpdir
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
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_load_checkpoint_metadata_falls_back_when_file_missing(self):
        tmpdir = Path("tmp") / f"checkpoint_utils_{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=False)
        try:
            checkpoint_dir = tmpdir / "checkpoint_77"
            checkpoint_dir.mkdir()

            metadata = load_checkpoint_metadata(checkpoint_dir)
            self.assertEqual(metadata["turn"], 77)
            self.assertEqual(metadata["name"], "checkpoint_77")
            self.assertIsNone(metadata["screen_type"])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_prune_old_checkpoints_keeps_latest_n(self):
        tmpdir = Path("tmp") / f"checkpoint_utils_{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=False)
        try:
            root = tmpdir
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
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_list_startup_checkpoints_includes_named_and_recent_turns(self):
        tmpdir = Path("tmp") / f"checkpoint_utils_{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=False)
        try:
            root = tmpdir
            named_dir = root / "milestone_route_1"
            named_dir.mkdir()
            (named_dir / "emulator.state").write_bytes(b"named")
            write_checkpoint_metadata(
                named_dir,
                build_checkpoint_metadata(
                    name=named_dir.name,
                    turn=125,
                    label="Milestone: Route 1",
                    kind="named",
                ),
            )

            for turn in (110, 120, 130):
                checkpoint_dir = root / f"checkpoint_{turn}"
                checkpoint_dir.mkdir()
                (checkpoint_dir / "emulator.state").write_bytes(b"turn")
                write_checkpoint_metadata(
                    checkpoint_dir,
                    build_checkpoint_metadata(name=checkpoint_dir.name, turn=turn),
                )

            checkpoints = list_startup_checkpoints(root, recent_turn_limit=2)

            self.assertEqual(
                [item["name"] for item in checkpoints],
                ["milestone_route_1", "checkpoint_130", "checkpoint_120"],
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_prune_old_checkpoints_does_not_delete_named_slots(self):
        tmpdir = Path("tmp") / f"checkpoint_utils_{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=False)
        try:
            root = tmpdir
            named_dir = root / "milestone_viridian_city"
            named_dir.mkdir()
            (named_dir / "emulator.state").write_bytes(b"named")
            write_checkpoint_metadata(
                named_dir,
                build_checkpoint_metadata(
                    name=named_dir.name,
                    turn=90,
                    label="Milestone: Viridian City",
                    kind="named",
                ),
            )

            for turn in (10, 20, 30):
                checkpoint_dir = root / f"checkpoint_{turn}"
                checkpoint_dir.mkdir()
                (checkpoint_dir / "emulator.state").write_bytes(b"turn")
                write_checkpoint_metadata(
                    checkpoint_dir,
                    build_checkpoint_metadata(name=checkpoint_dir.name, turn=turn),
                )

            removed = prune_old_checkpoints(root, keep_latest=1)

            self.assertEqual(sorted(path.name for path in removed), ["checkpoint_10", "checkpoint_20"])
            self.assertEqual(
                [item["name"] for item in list_checkpoints(root)],
                ["milestone_viridian_city", "checkpoint_30"],
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
