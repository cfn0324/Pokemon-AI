import unittest

import numpy as np

from main import PokemonAIAgent
from src.state.vision import VisionProcessor


class _ConfigStub:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)


class _MapMemoryStub:
    def __init__(self, frontier_plan):
        self.frontier_plan = frontier_plan

    def find_path_to_nearest_frontier(self, map_id, x, y, max_depth=40):
        return self.frontier_plan


class _MapMemoryAvoidanceStub:
    def __init__(self):
        self.frontiers = [
            {
                "position": (13, 4),
                "unknown_directions": ["right"],
                "visit_count": 20,
                "distance": 1,
            },
            {
                "position": (11, 4),
                "unknown_directions": ["left"],
                "visit_count": 5,
                "distance": 1,
            },
        ]

    def get_frontier_tiles(self, map_id, current_position=None):
        return list(self.frontiers)

    def find_shortest_path(self, map_id, start, target, max_depth=64):
        if tuple(target) == (13, 4):
            return ["right"]
        if tuple(target) == (11, 4):
            return ["left"]
        return None


class _MapMemoryCurrentFrontierBlockedStub:
    def __init__(self):
        self.frontiers = [
            {
                "position": (12, 4),
                "unknown_directions": ["right"],
                "visit_count": 1,
                "distance": 0,
            },
            {
                "position": (11, 4),
                "unknown_directions": ["left"],
                "visit_count": 2,
                "distance": 1,
            },
        ]

    def get_frontier_tiles(self, map_id, current_position=None):
        return list(self.frontiers)

    def find_shortest_path(self, map_id, start, target, max_depth=64):
        if tuple(target) == (12, 4):
            return []
        if tuple(target) == (11, 4):
            return ["left"]
        return None


class _MapMemoryNoveltyStub:
    def __init__(self):
        self.frontiers = [
            {
                "position": (13, 4),
                "unknown_directions": ["right"],
                "visit_count": 1,
                "distance": 1,
                "local_visit_pressure": 55,
                "global_novelty_distance": 1,
                "priority_score": -60.0,
                "novelty_label": "low",
            },
            {
                "position": (20, 4),
                "unknown_directions": ["up", "right"],
                "visit_count": 4,
                "distance": 8,
                "local_visit_pressure": 4,
                "global_novelty_distance": 9,
                "priority_score": 22.0,
                "novelty_label": "high",
            },
        ]

    def get_frontier_tiles(self, map_id, current_position=None):
        return list(self.frontiers)

    def find_shortest_path(self, map_id, start, target, max_depth=64):
        if tuple(target) == (13, 4):
            return ["right"]
        if tuple(target) == (20, 4):
            return ["up", "right", "right"]
        return None


class _LoggerStub:
    def info(self, *args, **kwargs):
        return None


class _MapMemoryRecordFailedMoveStub:
    def __init__(self):
        self.calls = []

    def record_failed_move(self, map_id, x, y, direction):
        self.calls.append((map_id, x, y, direction))


class _MainAgentStub:
    def __init__(self):
        self.notes = []

    def is_in_api_cooldown(self):
        return False

    def add_guidance_note(self, note, source=None):
        self.notes.append((note, source))


class _CriticStub:
    def __init__(self):
        self.calls = 0

    def critique(self, history, current_state):
        self.calls += 1
        return {"issues": "test", "suggestions": "test"}


class RuntimeSafeguardTests(unittest.TestCase):
    def test_vision_detects_blank_startup_transition(self):
        vision = VisionProcessor()
        blank = np.full((144, 160, 3), 255, dtype=np.uint8)

        ui = vision._detect_ui_elements(blank)

        self.assertEqual(vision._identify_screen_type(blank, ui), "startup")

    def test_trigger_tile_retreat_marks_frontier_as_temporarily_avoided(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"navigation.trigger_tile_avoid_turns": 25})
        agent.turn_count = 100
        agent.logger = _LoggerStub()
        agent.map_memory = _MapMemoryRecordFailedMoveStub()
        agent._planned_actions = []
        agent._planned_target = None
        agent._planned_reasoning = ""
        agent._temporarily_avoided_frontiers = {}
        agent._temporarily_avoided_moves = {}
        agent._pending_trigger_tile = {
            "origin": (1, 12, 4),
            "trigger": (1, 13, 4),
        }

        agent._update_trigger_tile_memory(
            {
                "memory": {
                    "position": {"map_id": 1, "x": 13, "y": 4},
                    "ui": {"text_box_active": True},
                }
            },
            {
                "memory": {
                    "position": {"map_id": 1, "x": 12, "y": 4},
                    "in_battle": False,
                    "ui": {"text_box_active": False},
                }
            },
            "left",
        )

        self.assertIn((1, 13, 4), agent._temporarily_avoided_frontiers)
        self.assertIn((1, 12, 4), agent._temporarily_avoided_frontiers)
        self.assertIn((1, 12, 4, "right"), agent._temporarily_avoided_moves)
        self.assertEqual(agent.map_memory.calls, [])

    def test_immediate_retreat_without_textbox_still_marks_move_avoided(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"navigation.trigger_tile_avoid_turns": 25})
        agent.turn_count = 100
        agent.logger = _LoggerStub()
        agent.map_memory = _MapMemoryRecordFailedMoveStub()
        agent._planned_actions = []
        agent._planned_target = None
        agent._planned_reasoning = ""
        agent._temporarily_avoided_frontiers = {}
        agent._temporarily_avoided_moves = {}
        agent._pending_trigger_tile = {
            "origin": (1, 34, 12),
            "trigger": (1, 35, 12),
        }

        agent._update_trigger_tile_memory(
            {
                "memory": {
                    "position": {"map_id": 1, "x": 35, "y": 12},
                    "ui": {"text_box_active": False},
                }
            },
            {
                "memory": {
                    "position": {"map_id": 1, "x": 34, "y": 12},
                    "in_battle": False,
                    "ui": {"text_box_active": False},
                }
            },
            "left",
        )

        self.assertIn((1, 34, 12, "right"), agent._temporarily_avoided_moves)
        self.assertEqual(
            agent.map_memory.calls,
            [
                (1, 34, 12, "right"),
                (1, 34, 12, "right"),
            ],
        )

    def test_navigation_plan_skips_temporarily_avoided_frontier(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "navigation.auto_plan_stall_turns": 3,
                "navigation.proactive_frontier_before_first_badge": True,
                "navigation.proactive_frontier_visit_threshold": 4,
                "navigation.max_plan_path_length": 24,
            }
        )
        agent._planned_actions = []
        agent._planned_target = None
        agent._planned_reasoning = ""
        agent._temporarily_avoided_frontiers = {(1, 13, 4): 999}
        agent._temporarily_avoided_moves = {}
        agent.map_memory = _MapMemoryAvoidanceStub()

        decision = agent._get_navigation_plan_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "in_battle": False,
                    "badge_count": 0,
                    "position": {"map_id": 1, "x": 12, "y": 4},
                },
                "deltas": {"movement_stall_turns": 0},
                "navigation": {
                    "current_visit_count": 6,
                    "blocked_directions": [],
                    "nearest_frontier": {
                        "target": (13, 4),
                        "path": ["right"],
                        "unknown_directions": ["right"],
                        "visit_count": 20,
                        "distance": 1,
                    },
                },
                "visual": {"navigation_hints": {}},
            },
            "overworld",
        )

        self.assertEqual(decision["action"], "left")

    def test_navigation_plan_skips_temporarily_avoided_first_step(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "navigation.auto_plan_stall_turns": 3,
                "navigation.proactive_frontier_before_first_badge": True,
                "navigation.proactive_frontier_visit_threshold": 4,
                "navigation.max_plan_path_length": 24,
            }
        )
        agent._planned_actions = []
        agent._planned_target = None
        agent._planned_reasoning = ""
        agent._temporarily_avoided_frontiers = {}
        agent._temporarily_avoided_moves = {(1, 12, 4, "right"): 999}
        agent.map_memory = _MapMemoryAvoidanceStub()

        decision = agent._get_navigation_plan_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "in_battle": False,
                    "badge_count": 0,
                    "position": {"map_id": 1, "x": 12, "y": 4},
                },
                "deltas": {"movement_stall_turns": 0},
                "navigation": {
                    "current_visit_count": 6,
                    "blocked_directions": [],
                    "nearest_frontier": {
                        "target": (13, 4),
                        "path": ["right"],
                        "unknown_directions": ["right"],
                        "visit_count": 20,
                        "distance": 1,
                    },
                },
                "visual": {"navigation_hints": {}},
            },
            "overworld",
        )

        self.assertEqual(decision["action"], "left")

    def test_navigation_plan_skips_current_frontier_when_all_unknown_directions_blocked(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "navigation.auto_plan_stall_turns": 3,
                "navigation.proactive_frontier_before_first_badge": True,
                "navigation.proactive_frontier_visit_threshold": 4,
                "navigation.max_plan_path_length": 24,
                "navigation.trigger_tile_avoid_turns": 25,
            }
        )
        agent.turn_count = 100
        agent.logger = _LoggerStub()
        agent._planned_actions = []
        agent._planned_target = None
        agent._planned_reasoning = ""
        agent._temporarily_avoided_frontiers = {}
        agent._temporarily_avoided_moves = {}
        agent.map_memory = _MapMemoryCurrentFrontierBlockedStub()

        decision = agent._get_navigation_plan_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "in_battle": False,
                    "badge_count": 0,
                    "position": {"map_id": 1, "x": 12, "y": 4},
                },
                "deltas": {"movement_stall_turns": 0},
                "navigation": {
                    "current_visit_count": 6,
                    "blocked_directions": ["right"],
                    "nearest_frontier": {
                        "target": (12, 4),
                        "path": [],
                        "unknown_directions": ["right"],
                        "visit_count": 1,
                        "distance": 0,
                    },
                },
                "visual": {"navigation_hints": {}},
            },
            "overworld",
        )

        self.assertEqual(decision["action"], "left")
        self.assertIn((1, 12, 4), agent._temporarily_avoided_frontiers)

    def test_navigation_plan_defers_to_ai_on_micro_loop_current_frontier(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "navigation.auto_plan_stall_turns": 3,
                "navigation.proactive_frontier_before_first_badge": True,
                "navigation.proactive_frontier_visit_threshold": 4,
                "navigation.max_plan_path_length": 24,
                "navigation.defer_to_ai_on_loop_warning": True,
                "navigation.loop_warning_visit_threshold": 12,
            }
        )
        agent._planned_actions = []
        agent._planned_target = None
        agent._planned_reasoning = ""
        agent._temporarily_avoided_frontiers = {}
        agent._temporarily_avoided_moves = {}
        agent.map_memory = _MapMemoryCurrentFrontierBlockedStub()

        decision = agent._get_navigation_plan_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "in_battle": False,
                    "badge_count": 0,
                    "position": {"map_id": 1, "x": 12, "y": 4},
                },
                "deltas": {"movement_stall_turns": 0},
                "movement_pattern": {
                    "micro_loop_warning": True,
                    "window_size": 8,
                    "unique_tiles": 3,
                    "bounding_box_width": 2,
                    "bounding_box_height": 2,
                },
                "navigation": {
                    "current_visit_count": 25,
                    "blocked_directions": [],
                    "nearest_frontier": {
                        "target": (12, 4),
                        "path": [],
                        "unknown_directions": ["right"],
                        "visit_count": 1,
                        "distance": 0,
                    },
                },
                "visual": {"navigation_hints": {}},
            },
            "overworld",
        )

        self.assertIsNone(decision)

    def test_guidance_interval_zero_disables_critic_guidance(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"ai.guidance_interval_turns": 0})
        agent.main_agent = _MainAgentStub()
        agent.critic = _CriticStub()
        agent.turn_count = 100
        agent._last_guidance_turn = 0

        agent._maybe_add_guidance_note(
            {
                "memory": {
                    "ui": {"text_box_active": False, "menu_active": False},
                    "in_battle": False,
                    "badge_count": 1,
                    "item_count": 0,
                    "position": {"map_id": 3, "x": 10, "y": 10},
                }
            },
            "overworld",
        )

        self.assertEqual(agent.critic.calls, 0)
        self.assertEqual(agent.main_agent.notes, [])

    def test_pre_starter_recovery_skips_pre_world_boot_state(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub()

        decision = agent._get_pre_starter_recovery_move_decision(
            {
                "pre_world": True,
                "memory": {
                    "party": [],
                    "in_battle": False,
                },
                "deltas": {"movement_stall_turns": 8},
                "navigation": {"blocked_directions": []},
                "visual": {"navigation_hints": {}},
            },
            "overworld",
        )

        self.assertIsNone(decision)

    def test_navigation_plan_engages_early_on_revisited_frontier_tiles(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "navigation.auto_plan_stall_turns": 3,
                "navigation.proactive_frontier_before_first_badge": True,
                "navigation.proactive_frontier_visit_threshold": 4,
            }
        )
        agent._planned_actions = []
        agent._planned_target = None
        agent._planned_reasoning = ""
        agent.map_memory = _MapMemoryStub(
            {
                "target": (22, 10),
                "path": [],
                "unknown_directions": ["up"],
                "visit_count": 9,
                "distance": 0,
            }
        )

        decision = agent._get_navigation_plan_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "in_battle": False,
                    "badge_count": 0,
                    "position": {"map_id": 1, "x": 22, "y": 10},
                },
                "deltas": {"movement_stall_turns": 0},
                "navigation": {
                    "current_visit_count": 1,
                    "blocked_directions": [],
                    "nearest_frontier": {
                        "target": (22, 10),
                        "path": [],
                        "unknown_directions": ["up"],
                        "visit_count": 9,
                        "distance": 0,
                    },
                },
                "visual": {"navigation_hints": {}},
            },
            "overworld",
        )

        self.assertEqual(decision["action"], "up")

    def test_navigation_frontier_plan_prefers_more_novel_lower_pressure_target(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"navigation.max_plan_path_length": 24})
        agent._temporarily_avoided_frontiers = {}
        agent._temporarily_avoided_moves = {}
        agent.map_memory = _MapMemoryNoveltyStub()

        plan = agent._get_navigation_frontier_plan(
            {
                "memory": {
                    "position": {"map_id": 1, "x": 12, "y": 4},
                },
                "navigation": {
                    "nearest_frontier": None,
                },
            }
        )

        self.assertEqual(tuple(plan["target"]), (20, 4))
        self.assertEqual(plan["novelty_label"], "high")
        self.assertEqual(plan["path"][0], "up")

    def test_research_mode_stage_specs_drop_fixed_route_controllers(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"decision.research_mode": True})

        stage_names = [name for name, _ in agent._get_decision_stage_specs()]

        self.assertNotIn("oak_lab_starter", stage_names)
        self.assertNotIn("oak_lab_rival_battle", stage_names)
        self.assertNotIn("post_battle_intro_route", stage_names)
        self.assertIn("known_ui", stage_names)
        self.assertIn("navigation_plan", stage_names)

    def test_default_stage_specs_keep_fixed_route_controllers(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({})

        stage_names = [name for name, _ in agent._get_decision_stage_specs()]

        self.assertIn("oak_lab_starter", stage_names)
        self.assertIn("oak_lab_rival_battle", stage_names)
        self.assertIn("post_battle_intro_route", stage_names)


if __name__ == "__main__":
    unittest.main()
