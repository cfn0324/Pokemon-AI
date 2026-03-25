import queue
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from main import PokemonAIAgent, _prompt_for_startup_checkpoint


class _ConfigStub:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class _LoggerStub:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def milestone(self, *args, **kwargs):
        return None


class _VisualizerStub:
    def __init__(self):
        self.events = []

    def log_event(self, kind, message):
        self.events.append((kind, message))

    def update_checkpoints(self, *_args, **_kwargs):
        return None

    def update_control_state(self, *_args, **_kwargs):
        return None


class CheckpointRuntimeTests(unittest.TestCase):
    def test_prompt_for_startup_checkpoint_selects_indexed_checkpoint(self):
        config = _ConfigStub(
            {
                "game.prompt_for_checkpoint_on_start": True,
                "game.save_state_dir": "data/checkpoints",
                "game.startup_checkpoint_recent_limit": 4,
                "game.resume_checkpoint": None,
                "game.auto_resume_latest_checkpoint": True,
                "visualization.enabled": False,
            }
        )

        with patch("main.list_startup_checkpoints", return_value=[
            {"name": "milestone_route_1", "label": "Milestone: Route 1", "turn": 120, "position": {"map_id": 12, "x": 5, "y": 0}, "kind": "named"},
            {"name": "checkpoint_150", "label": "Turn 150", "turn": 150, "position": {"map_id": 1, "x": 33, "y": 12}, "kind": "turn"},
        ]), patch("main.sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="2"), patch("builtins.print"):
            _prompt_for_startup_checkpoint(config)

        self.assertEqual(config.get("game.resume_checkpoint"), "checkpoint_150")
        self.assertFalse(config.get("game.auto_resume_latest_checkpoint"))

    def test_prompt_for_startup_checkpoint_skips_cli_when_visualization_enabled(self):
        config = _ConfigStub(
            {
                "game.prompt_for_checkpoint_on_start": True,
                "visualization.enabled": True,
                "game.resume_checkpoint": None,
                "game.auto_resume_latest_checkpoint": True,
            }
        )

        with patch("builtins.input", side_effect=AssertionError("input should not be called")):
            _prompt_for_startup_checkpoint(config)

        self.assertIsNone(config.get("game.resume_checkpoint"))
        self.assertTrue(config.get("game.auto_resume_latest_checkpoint"))

    def test_checkpoint_spec_matches_position_direction_and_party_limits(self):
        agent = object.__new__(PokemonAIAgent)
        state = {
            "pre_world": False,
            "pre_starter_script": False,
            "memory": {
                "position": {"map_id": 1, "x": 33, "y": 12},
                "direction": "up",
                "party": [{"species": "Pikachu"}],
                "badge_count": 0,
                "in_battle": False,
                "ui": {"text_box_active": False},
            },
            "visual": {"screen_type": "overworld"},
        }
        spec = {
            "name": "milestone_viridian_city",
            "map_id": 1,
            "x": 33,
            "y": 12,
            "direction": "up",
            "min_party_size": 1,
            "max_badges": 0,
            "screen_type": "overworld",
        }

        self.assertTrue(agent._checkpoint_spec_matches(spec, state))
        self.assertFalse(agent._checkpoint_spec_matches({**spec, "direction": "left"}, state))
        self.assertFalse(agent._checkpoint_spec_matches({**spec, "min_party_size": 2}, state))

    def test_maybe_save_landmark_checkpoints_only_saves_on_new_match(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "testing.write_checkpoints": True,
                "game.landmark_checkpoints_enabled": True,
                "game.landmark_checkpoints": {
                    "milestone_viridian_city": {
                        "label": "Milestone: Viridian City",
                        "map_id": 1,
                        "min_party_size": 1,
                        "max_badges": 0,
                    }
                },
                "visualization.enabled": False,
            }
        )
        agent._active_landmark_checkpoints = set()
        agent.logger = _LoggerStub()
        saved = []

        def fake_write(checkpoint_name, *, kind, label=None, current_state=None):
            saved.append((checkpoint_name, kind, label, current_state["memory"]["position"]["map_id"]))
            return Path("data/checkpoints") / checkpoint_name, {"name": checkpoint_name}

        agent._write_checkpoint_bundle = fake_write

        match_state = {
            "memory": {
                "position": {"map_id": 1, "x": 33, "y": 12},
                "direction": "up",
                "party": [{"species": "Pikachu"}],
                "badge_count": 0,
                "in_battle": False,
                "ui": {"text_box_active": False},
            },
            "visual": {"screen_type": "overworld"},
        }
        other_state = {
            "memory": {
                "position": {"map_id": 12, "x": 5, "y": 0},
                "direction": "up",
                "party": [{"species": "Pikachu"}],
                "badge_count": 0,
                "in_battle": False,
                "ui": {"text_box_active": False},
            },
            "visual": {"screen_type": "overworld"},
        }

        agent._maybe_save_landmark_checkpoints(match_state)
        agent._maybe_save_landmark_checkpoints(match_state)
        agent._maybe_save_landmark_checkpoints(other_state)
        agent._maybe_save_landmark_checkpoints(match_state)

        self.assertEqual(
            saved,
            [
                ("milestone_viridian_city", "named", "Milestone: Viridian City", 1),
                ("milestone_viridian_city", "named", "Milestone: Viridian City", 1),
            ],
        )

    def test_handle_visualizer_command_load_checkpoint_pauses_and_clears_queue(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "visualization.enabled": True,
                "game.auto_resume_latest_checkpoint": False,
            }
        )
        agent.logger = _LoggerStub()
        agent.visualizer = _VisualizerStub()
        agent._control_lock = threading.Lock()
        agent._paused = False
        agent._step_budget = 3
        agent._checkpoint_requested = False
        agent._manual_actions = queue.Queue()
        agent._manual_actions.put("up")
        agent._manual_actions.put("left")
        agent._last_control_command = ""
        agent._last_control_timestamp = None
        agent._last_control_error = None
        agent._restored_checkpoint_name = None
        agent.running = True
        loaded = []

        def fake_load(name, pause_after_load=False):
            loaded.append((name, pause_after_load))
            agent._paused = pause_after_load
            agent._restored_checkpoint_name = name
            return {"name": name}

        agent._load_checkpoint = fake_load
        agent.get_available_checkpoints = lambda limit=20: [{"name": "checkpoint_30"}]
        agent._broadcast_control_state = lambda: None
        agent.get_visualizer_control_state = lambda: {
            "paused": agent._paused,
            "step_budget": agent._step_budget,
        }

        result = agent.handle_visualizer_command("load_checkpoint", "milestone_route_1")

        self.assertTrue(result["ok"])
        self.assertEqual(loaded, [("milestone_route_1", True)])
        self.assertEqual(agent._step_budget, 0)
        self.assertTrue(agent._manual_actions.empty())
        self.assertEqual(agent._last_control_command, "load_checkpoint:milestone_route_1")

    def test_maybe_restore_initial_checkpoint_uses_dashboard_selection_when_visualizer_enabled(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "game.prompt_for_checkpoint_on_start": True,
                "visualization.enabled": True,
                "game.resume_checkpoint": None,
                "game.auto_resume_latest_checkpoint": True,
            }
        )
        agent.logger = _LoggerStub()
        agent.visualizer = _VisualizerStub()
        agent._control_lock = threading.Lock()
        agent._paused = False
        agent._startup_selection_pending = False
        agent.get_available_checkpoints = lambda limit=20: [{"name": "checkpoint_30"}]
        agent.get_startup_checkpoint_choices = lambda: [{"name": "checkpoint_30"}]
        agent._broadcast_control_state = lambda: None
        loaded = []
        agent._load_checkpoint = lambda *args, **kwargs: loaded.append((args, kwargs))

        agent._maybe_restore_initial_checkpoint()

        self.assertTrue(agent._paused)
        self.assertTrue(agent._startup_selection_pending)
        self.assertEqual(loaded, [])

    def test_handle_visualizer_command_resume_clears_startup_selection_pending(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"visualization.enabled": True})
        agent.logger = _LoggerStub()
        agent.visualizer = _VisualizerStub()
        agent._control_lock = threading.Lock()
        agent._paused = True
        agent._step_budget = 0
        agent._checkpoint_requested = False
        agent._manual_actions = queue.Queue()
        agent._last_control_command = ""
        agent._last_control_timestamp = None
        agent._last_control_error = None
        agent._startup_selection_pending = True
        agent.running = True
        agent.get_available_checkpoints = lambda limit=20: []
        agent.get_startup_checkpoint_choices = lambda: []
        agent._broadcast_control_state = lambda: None
        agent.get_visualizer_control_state = lambda: {
            "paused": agent._paused,
            "startup_selection_pending": agent._startup_selection_pending,
        }

        result = agent.handle_visualizer_command("resume")

        self.assertTrue(result["ok"])
        self.assertFalse(agent._paused)
        self.assertFalse(agent._startup_selection_pending)


if __name__ == "__main__":
    unittest.main()
