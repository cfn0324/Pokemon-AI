import json
import shutil
import unittest
import uuid
from pathlib import Path

from src.memory.context_manager import ContextManager


class ContextManagerLoadTests(unittest.TestCase):
    def test_load_replaces_existing_recent_turns(self):
        manager = ContextManager(max_turns=5, keep_recent=2)
        manager.add_turn(1, {"memory": {}}, action="a", reasoning="first")

        tmpdir = Path("tmp") / f"context_manager_{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=False)
        try:
            path = tmpdir / "context.json"
            path.write_text(
                json.dumps(
                    {
                        "summaries": [],
                        "notes": [],
                        "recent_turns": [
                            {
                                "turn_number": 7,
                                "timestamp": "2026-03-22T00:00:00",
                                "action": "b",
                                "reasoning": "loaded",
                                "result": "ok",
                            }
                        ],
                        "current_period_start": 0,
                    }
                ),
                encoding="utf-8",
            )

            manager.load(str(path))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertEqual(len(manager.recent_turns), 1)
        self.assertEqual(manager.recent_turns[0].turn_number, 7)
        self.assertEqual(manager.recent_turns[0].action, "b")


if __name__ == "__main__":
    unittest.main()
