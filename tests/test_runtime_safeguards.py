import unittest
from types import SimpleNamespace

import numpy as np

from main import PokemonAIAgent
from src.control.post_battle_intro_route import PostBattleIntroRouteController
from src.control.post_pokedex_departure_controller import PostPokedexDepartureController
from src.control.viridian_parcel_controller import ViridianParcelController
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


class _ActionExecutorStub:
    def __init__(self, history=None):
        self.history = list(history or [])

    def get_action_history(self, count):
        return self.history[-count:]


class RuntimeSafeguardTests(unittest.TestCase):
    def test_synchronize_runtime_turn_state_uses_agent_turn_count(self):
        agent = object.__new__(PokemonAIAgent)
        agent.turn_count = 123
        agent.game_state = SimpleNamespace(turn_count=999)

        state = agent._synchronize_runtime_turn_state(
            {
                "turn": 999,
                "memory": {"position": {"map_id": 1, "x": 2, "y": 3}},
            }
        )

        self.assertEqual(state["turn"], 123)
        self.assertEqual(agent.game_state.turn_count, 123)

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

    def test_trigger_tile_retreat_during_wait_still_marks_move_avoided(self):
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
            "origin": (1, 19, 10),
            "trigger": (1, 19, 9),
        }

        agent._update_trigger_tile_memory(
            {
                "memory": {
                    "position": {"map_id": 1, "x": 19, "y": 9},
                    "ui": {"text_box_active": False},
                },
                "visual": {"screen_type": "overworld"},
            },
            {
                "memory": {
                    "position": {"map_id": 1, "x": 19, "y": 10},
                    "in_battle": False,
                    "ui": {"text_box_active": True},
                },
                "visual": {"screen_type": "dialogue"},
            },
            "wait",
        )

        self.assertIn((1, 19, 10, "up"), agent._temporarily_avoided_moves)
        self.assertIn((1, 19, 9), agent._temporarily_avoided_frontiers)
        self.assertIn((1, 19, 10), agent._temporarily_avoided_frontiers)
        self.assertEqual(agent.map_memory.calls, [])

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

    def test_navigation_plan_skips_known_blocked_first_step(self):
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
                    "blocked_directions": ["right"],
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

    def test_control_screen_type_ignores_false_naming_screen_in_oak_lab_dialogue(self):
        agent = object.__new__(PokemonAIAgent)

        screen_type = agent._get_control_screen_type(
            {
                "phase_hint": "dialogue",
                "memory": {
                    "in_battle": False,
                    "badge_count": 0,
                    "party": [],
                    "position": {"map_id": 40, "x": 5, "y": 3},
                    "ui": {"text_box_active": True, "menu_active": False},
                },
            },
            "naming_screen",
        )

        self.assertEqual(screen_type, "dialogue")

    def test_control_screen_type_preserves_real_naming_screen_after_starter(self):
        agent = object.__new__(PokemonAIAgent)

        screen_type = agent._get_control_screen_type(
            {
                "phase_hint": "naming_screen",
                "memory": {
                    "in_battle": False,
                    "badge_count": 0,
                    "party": [{"species": "Charmander"}],
                    "position": {"map_id": 40, "x": 5, "y": 3},
                    "ui": {"text_box_active": True, "menu_active": False},
                },
            },
            "naming_screen",
        )

        self.assertEqual(screen_type, "naming_screen")

    def test_control_screen_type_ignores_false_battle_detection_after_field_control_returns(self):
        agent = object.__new__(PokemonAIAgent)
        agent._prev_screen_type = "indoor"

        screen_type = agent._get_control_screen_type(
            {
                "phase_hint": "unknown",
                "pre_world": False,
                "pre_starter_script": False,
                "battle_summary": {"phase": "not_in_battle"},
                "memory": {
                    "in_battle": False,
                    "party": [{"species": "Charmander"}],
                    "position": {"map_id": 51, "x": 17, "y": 45},
                    "ui": {"text_box_active": False, "menu_active": True},
                },
            },
            "battle",
        )

        self.assertEqual(screen_type, "indoor")

    def test_normalize_ui_flags_clears_stale_menu_after_false_battle_detection(self):
        agent = object.__new__(PokemonAIAgent)
        agent.game_state = SimpleNamespace(_movement_stall_turns=0)

        current_state = {
            "pre_world": False,
            "pre_starter_script": False,
            "visual": {"screen_type": "indoor", "observed_screen_type": "battle"},
            "battle_summary": {"phase": "not_in_battle"},
            "memory": {
                "in_battle": False,
                "party": [{"species": "Charmander"}],
                "position": {"map_id": 51, "x": 17, "y": 45},
                "ui": {"text_box_active": False, "menu_active": True},
            },
            "deltas": {"position_changed": False},
        }

        agent._normalize_ui_flags_for_control(current_state, "indoor")

        self.assertFalse(current_state["memory"]["ui"]["menu_active"])
        self.assertTrue(current_state["memory"]["ui"]["stale_menu_flag"])
        self.assertTrue(current_state["visual"]["stale_battle_screen_flag"])

    def test_control_screen_type_preserves_recent_battle_observation_during_transient_flag_drop(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"actions.recent_battle_visual_grace_turns": 2})
        agent._recent_battle_visual_grace_turns = 0
        agent._prev_screen_type = None

        confirmed_battle = {
            "pre_world": False,
            "pre_starter_script": False,
            "phase_hint": "battle",
            "battle_summary": {"phase": "battle_in_progress"},
            "memory": {
                "in_battle": True,
                "position": {"map_id": 12, "x": 11, "y": 33},
                "ui": {"text_box_active": True, "menu_active": False},
            },
        }
        transient_drop = {
            "pre_world": False,
            "pre_starter_script": False,
            "phase_hint": "battle",
            "battle_summary": {"phase": "not_in_battle"},
            "memory": {
                "in_battle": False,
                "party": [{"species": "Charmander"}],
                "position": {"map_id": 12, "x": 11, "y": 33},
                "ui": {"text_box_active": False, "menu_active": False},
            },
        }

        self.assertEqual(agent._get_control_screen_type(confirmed_battle, "battle"), "battle")
        self.assertEqual(agent._recent_battle_visual_grace_turns, 2)
        self.assertEqual(agent._get_control_screen_type(transient_drop, "battle"), "battle")
        self.assertEqual(agent._recent_battle_visual_grace_turns, 1)
        self.assertEqual(agent._get_control_screen_type(transient_drop, "battle"), "battle")
        self.assertEqual(agent._recent_battle_visual_grace_turns, 0)
        self.assertEqual(agent._get_control_screen_type(transient_drop, "battle"), "overworld")

    def test_normalize_ui_flags_clears_stale_menu_on_field_screen(self):
        agent = object.__new__(PokemonAIAgent)
        agent.game_state = SimpleNamespace(_movement_stall_turns=0)

        current_state = {
            "pre_world": False,
            "pre_starter_script": False,
            "visual": {"screen_type": "overworld"},
            "battle_summary": {"phase": "not_in_battle"},
            "memory": {
                "in_battle": False,
                "party": [{"species": "Charmander"}],
                "position": {"map_id": 51, "x": 18, "y": 43},
                "ui": {"text_box_active": False, "menu_active": True},
            },
            "deltas": {"position_changed": False},
        }

        agent._normalize_ui_flags_for_control(current_state, "overworld")

        self.assertFalse(current_state["memory"]["ui"]["menu_active"])
        self.assertTrue(current_state["memory"]["ui"]["stale_menu_flag"])
        self.assertEqual(current_state["deltas"]["movement_stall_turns"], 1)
        self.assertEqual(current_state["deltas"]["stuck_hint"], "slight stall")

    def test_known_ui_skips_oak_lab_nickname_entry_with_b(self):
        agent = object.__new__(PokemonAIAgent)
        agent._scripted_ui_actions = []
        agent._scripted_ui_reasoning = ""

        decision = agent._get_known_ui_decision(
            {
                "memory": {
                    "badge_count": 0,
                    "party": [{"species": "Charmander"}],
                    "position": {"map_id": 40, "x": 5, "y": 3},
                }
            },
            "naming_screen",
        )

        self.assertEqual(decision["action"], "b")

    def test_minimal_known_ui_leaves_nickname_choice_to_ai(self):
        agent = object.__new__(PokemonAIAgent)

        decision = agent._get_minimal_known_ui_decision(
            {
                "memory": {
                    "badge_count": 0,
                    "party": [{"species": "Charmander"}],
                    "position": {"map_id": 40, "x": 5, "y": 3},
                }
            },
            "naming_screen",
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

    def test_ai_error_fallback_uses_navigation_plan_in_field(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "decision.pure_llm_mode": False,
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
        agent._temporarily_avoided_moves = {}
        agent.map_memory = _MapMemoryAvoidanceStub()

        decision = agent._apply_ai_unavailable_fallback(
            {
                "action": "wait",
                "reasoning": "Error occurred: transport failure",
                "goal_update": None,
                "recorded_in_context": False,
                "decision_source": "ai_error",
                "decision_path": "ai",
            },
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
        self.assertEqual(decision["decision_source"], "api_unavailable_navigation_fallback")
        self.assertEqual(decision["decision_path"], "fallback")

    def test_ai_error_fallback_probes_blocked_field_with_interaction(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"decision.pure_llm_mode": False})
        agent.action_executor = _ActionExecutorStub(history=["wait", "wait"])
        agent._planned_actions = []
        agent._planned_target = None
        agent._planned_reasoning = ""
        agent._temporarily_avoided_frontiers = {}
        agent._temporarily_avoided_moves = {}
        agent.map_memory = _MapMemoryStub(None)

        decision = agent._apply_ai_unavailable_fallback(
            {
                "action": "wait",
                "reasoning": "Error occurred: transport failure",
                "goal_update": None,
                "recorded_in_context": False,
                "decision_source": "ai_error",
                "decision_path": "ai",
            },
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "in_battle": False,
                    "badge_count": 0,
                    "party": [{"species": "Charmander"}],
                    "position": {"map_id": 40, "x": 5, "y": 3},
                },
                "deltas": {"movement_stall_turns": 1},
                "movement_pattern": {"micro_loop_warning": True},
                "navigation": {
                    "current_visit_count": 200,
                    "blocked_directions": ["up", "down", "left", "right"],
                    "nearest_frontier": None,
                },
                "visual": {"navigation_hints": {"blocked_directions": ["up", "down", "left", "right"]}},
            },
            "indoor",
        )

        self.assertEqual(decision["action"], "a")
        self.assertEqual(decision["decision_source"], "api_unavailable_field_interaction")

    def test_ai_unavailable_dialogue_fallback_uses_stable_ui_recovery_after_repeated_a(self):
        agent = object.__new__(PokemonAIAgent)
        agent._stable_screen_turns = 9
        agent._dialogue_exit_grace = 0
        agent.action_executor = _ActionExecutorStub(history=["a"] * 6)
        agent._recent_actions_are_same = (
            PokemonAIAgent._recent_actions_are_same.__get__(agent, PokemonAIAgent)
        )
        agent._get_stable_ui_recovery_decision = (
            PokemonAIAgent._get_stable_ui_recovery_decision.__get__(agent, PokemonAIAgent)
        )
        agent._decorate_api_fallback_decision = (
            PokemonAIAgent._decorate_api_fallback_decision.__get__(agent, PokemonAIAgent)
        )
        agent._get_safe_battle_progress_decision = (
            PokemonAIAgent._get_safe_battle_progress_decision.__get__(agent, PokemonAIAgent)
        )

        decision = PokemonAIAgent._get_ai_unavailable_fallback_decision(
            agent,
            {
                "memory": {
                    "in_battle": False,
                    "ui": {"text_box_active": True, "menu_active": False},
                },
                "battle_summary": {"phase": "not_in_battle"},
            },
            "dialogue",
        )

        self.assertEqual(decision["action"], "b")
        self.assertEqual(decision["decision_source"], "api_unavailable_ui_recovery")

    def test_ai_unavailable_dialogue_exit_grace_uses_movement_instead_of_reopening_dialogue(self):
        agent = object.__new__(PokemonAIAgent)
        agent._stable_screen_turns = 1
        agent._dialogue_exit_grace = 2
        agent.action_executor = _ActionExecutorStub(history=["a"] * 2)
        agent._recent_actions_are_same = (
            PokemonAIAgent._recent_actions_are_same.__get__(agent, PokemonAIAgent)
        )
        agent._get_stable_ui_recovery_decision = (
            PokemonAIAgent._get_stable_ui_recovery_decision.__get__(agent, PokemonAIAgent)
        )
        agent._decorate_api_fallback_decision = (
            PokemonAIAgent._decorate_api_fallback_decision.__get__(agent, PokemonAIAgent)
        )
        agent._get_safe_battle_progress_decision = (
            PokemonAIAgent._get_safe_battle_progress_decision.__get__(agent, PokemonAIAgent)
        )
        agent._get_local_safe_exploration_decision = lambda *_args, **_kwargs: None
        agent._choose_recovery_move = lambda *_args, **_kwargs: "down"

        decision = PokemonAIAgent._get_ai_unavailable_fallback_decision(
            agent,
            {
                "memory": {
                    "in_battle": False,
                    "ui": {"text_box_active": False, "menu_active": False},
                },
                "battle_summary": {"phase": "not_in_battle"},
            },
            "overworld",
        )

        self.assertEqual(decision["action"], "down")
        self.assertEqual(decision["decision_source"], "api_unavailable_dialogue_exit_recovery")

    def test_local_safe_exploration_retries_known_exit_even_if_blocked_memory_lists_every_direction(self):
        agent = object.__new__(PokemonAIAgent)
        agent._temporarily_avoided_moves = {}
        agent._prune_temporarily_avoided_moves = lambda: None

        decision = agent._get_local_safe_exploration_decision(
            {
                "memory": {
                    "position": {"map_id": 0, "x": 8, "y": 2},
                },
                "navigation": {
                    "blocked_directions": ["up", "down", "left", "right"],
                    "adjacent_tiles": {
                        "up": {"status": "blocked_once", "target_is_warp": False, "step_triggers_warp": False},
                        "down": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                        "left": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                        "right": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                    },
                },
                "visual": {"navigation_hints": {"blocked_directions": []}},
                "exploration": {"nearby_unexplored": []},
            },
            "overworld",
        )

        self.assertEqual(decision["action"], "left")

    def test_local_safe_exploration_prefers_forced_navigation_plan_on_micro_loop(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"navigation.local_fallback_force_plan_visit_threshold": 8})
        agent._get_navigation_plan_decision = lambda *_args, **_kwargs: {
            "action": "up",
            "reasoning": "Planner: follow learned route toward a better frontier",
            "goal_update": None,
            "recorded_in_context": False,
        }

        decision = agent._get_local_safe_exploration_decision(
            {
                "memory": {
                    "in_battle": False,
                    "position": {"map_id": 51, "x": 8, "y": 40},
                },
                "movement_pattern": {"micro_loop_warning": True},
                "navigation": {
                    "current_visit_count": 12,
                    "frontier_guidance": {"prefer_leave_current_frontier": True},
                },
                "visual": {"navigation_hints": {}},
            },
            "overworld",
        )

        self.assertEqual(decision["action"], "up")
        self.assertIn("learned frontier route", decision["reasoning"])

    def test_retryable_field_directions_skip_temporarily_avoided_known_exit(self):
        agent = object.__new__(PokemonAIAgent)
        agent._temporarily_avoided_moves = {(51, 18, 32, "left"): 999999}
        agent._prune_temporarily_avoided_moves = lambda: None
        agent._is_temporarily_avoided_move = (
            PokemonAIAgent._is_temporarily_avoided_move.__get__(agent, PokemonAIAgent)
        )

        retryable = PokemonAIAgent._get_retryable_field_directions(
            agent,
            {
                "memory": {
                    "position": {"map_id": 51, "x": 18, "y": 32},
                },
                "navigation": {
                    "blocked_directions": ["up", "left", "right"],
                    "adjacent_tiles": {
                        "up": {"status": "confirmed_blocked", "target_is_warp": False, "step_triggers_warp": False},
                        "down": {"status": "adjacent_explored", "target_is_warp": False, "step_triggers_warp": False},
                        "left": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                        "right": {"status": "confirmed_blocked", "target_is_warp": False, "step_triggers_warp": False},
                    },
                },
                "visual": {"navigation_hints": {"blocked_directions": []}},
            },
        )

        self.assertEqual(retryable, {"down"})

    def test_local_safe_exploration_avoids_temporarily_blacklisted_known_exit(self):
        agent = object.__new__(PokemonAIAgent)
        agent._temporarily_avoided_moves = {(51, 18, 32, "left"): 999999}
        agent._prune_temporarily_avoided_moves = lambda: None
        agent._is_temporarily_avoided_move = (
            PokemonAIAgent._is_temporarily_avoided_move.__get__(agent, PokemonAIAgent)
        )
        agent._get_retryable_field_directions = (
            PokemonAIAgent._get_retryable_field_directions.__get__(agent, PokemonAIAgent)
        )
        agent._get_navigation_plan_decision = lambda *_args, **_kwargs: None

        decision = agent._get_local_safe_exploration_decision(
            {
                "memory": {
                    "in_battle": False,
                    "position": {"map_id": 51, "x": 18, "y": 32},
                },
                "movement_pattern": {"micro_loop_warning": False},
                "navigation": {
                    "current_visit_count": 1,
                    "blocked_directions": ["up", "left", "right"],
                    "frontier_guidance": {},
                    "adjacent_tiles": {
                        "up": {"status": "confirmed_blocked", "target_is_warp": False, "step_triggers_warp": False},
                        "down": {"status": "adjacent_explored", "target_is_warp": False, "step_triggers_warp": False},
                        "left": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                        "right": {"status": "confirmed_blocked", "target_is_warp": False, "step_triggers_warp": False},
                    },
                },
                "visual": {"navigation_hints": {"blocked_directions": []}},
                "exploration": {"nearby_unexplored": []},
            },
            "overworld",
        )

        self.assertEqual(decision["action"], "down")

    def test_blocked_field_interaction_abstains_when_known_exit_is_still_retryable(self):
        agent = object.__new__(PokemonAIAgent)
        agent._temporarily_avoided_moves = {}
        agent._prune_temporarily_avoided_moves = lambda: None
        agent.action_executor = _ActionExecutorStub(history=["wait", "wait"])

        decision = agent._get_blocked_field_interaction_decision(
            {
                "memory": {
                    "in_battle": False,
                    "position": {"map_id": 0, "x": 8, "y": 2},
                },
                "navigation": {
                    "blocked_directions": ["up", "down", "left", "right"],
                    "adjacent_tiles": {
                        "left": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                        "right": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                    },
                },
                "visual": {"navigation_hints": {"blocked_directions": ["up", "down", "left", "right"]}},
            },
            "overworld",
        )

        self.assertIsNone(decision)

    def test_retryable_field_directions_drop_known_exit_when_temporarily_avoided(self):
        agent = object.__new__(PokemonAIAgent)
        agent._temporarily_avoided_moves = {
            (0, 3, 2, "down"): 999,
            (0, 3, 2, "left"): 999,
            (0, 3, 2, "right"): 999,
        }
        agent._prune_temporarily_avoided_moves = lambda: None

        retryable = agent._get_retryable_field_directions(
            {
                "memory": {
                    "position": {"map_id": 0, "x": 3, "y": 2},
                },
                "navigation": {
                    "blocked_directions": ["up", "down", "left", "right"],
                    "adjacent_tiles": {
                        "up": {"status": "confirmed_blocked", "target_is_warp": False, "step_triggers_warp": False},
                        "down": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                        "left": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                        "right": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                    },
                },
                "visual": {"navigation_hints": {"blocked_directions": ["up", "down", "left", "right"]}},
            }
        )

        self.assertEqual(retryable, set())

    def test_blocked_field_interaction_probes_when_all_known_exits_are_temporarily_avoided(self):
        agent = object.__new__(PokemonAIAgent)
        agent._temporarily_avoided_moves = {
            (0, 3, 2, "down"): 999,
            (0, 3, 2, "left"): 999,
            (0, 3, 2, "right"): 999,
        }
        agent._prune_temporarily_avoided_moves = lambda: None
        agent.action_executor = _ActionExecutorStub(history=["wait", "wait"])

        decision = agent._get_blocked_field_interaction_decision(
            {
                "memory": {
                    "in_battle": False,
                    "position": {"map_id": 0, "x": 3, "y": 2},
                },
                "navigation": {
                    "blocked_directions": ["up", "down", "left", "right"],
                    "adjacent_tiles": {
                        "up": {"status": "confirmed_blocked", "target_is_warp": False, "step_triggers_warp": False},
                        "down": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                        "left": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                        "right": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                    },
                },
                "visual": {"navigation_hints": {"blocked_directions": ["up", "down", "left", "right"]}},
            },
            "overworld",
        )

        self.assertEqual(decision["action"], "a")

    def test_temporarily_avoided_field_recovery_retries_single_known_exit(self):
        agent = object.__new__(PokemonAIAgent)
        agent._temporarily_avoided_moves = {
            (40, 8, 11, "right"): 999,
        }
        agent._prune_temporarily_avoided_moves = lambda: None
        agent._is_temporarily_avoided_move = (
            PokemonAIAgent._is_temporarily_avoided_move.__get__(agent, PokemonAIAgent)
        )
        agent._get_retryable_field_directions = (
            PokemonAIAgent._get_retryable_field_directions.__get__(agent, PokemonAIAgent)
        )

        decision = agent._get_temporarily_avoided_field_recovery_decision(
            {
                "memory": {
                    "in_battle": False,
                    "position": {"map_id": 40, "x": 8, "y": 11},
                },
                "navigation": {
                    "blocked_directions": ["up", "down", "left", "right"],
                    "adjacent_tiles": {
                        "up": {"status": "confirmed_blocked", "target_is_warp": False, "step_triggers_warp": False},
                        "down": {"status": "confirmed_blocked", "target_is_warp": False, "step_triggers_warp": False},
                        "left": {"status": "confirmed_blocked", "target_is_warp": False, "step_triggers_warp": False},
                        "right": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                    },
                },
                "visual": {"navigation_hints": {"blocked_directions": ["up", "down", "left"]}},
            },
            "indoor",
        )

        self.assertEqual(decision["action"], "right")
        self.assertIn("previously successful non-warp path", decision["reasoning"])

    def test_llm_primary_ai_error_fallback_does_not_invoke_navigation_plan(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "decision.pure_llm_mode": False,
                "decision.llm_primary_mode": True,
                "navigation.auto_plan_stall_turns": 3,
                "navigation.proactive_frontier_before_first_badge": True,
                "navigation.proactive_frontier_visit_threshold": 4,
                "navigation.max_plan_path_length": 24,
            }
        )
        agent.action_executor = _ActionExecutorStub(history=["wait", "wait"])
        agent._planned_actions = []
        agent._planned_target = None
        agent._planned_reasoning = ""
        agent._temporarily_avoided_frontiers = {}
        agent._temporarily_avoided_moves = {}
        agent.map_memory = _MapMemoryAvoidanceStub()

        decision = agent._apply_ai_unavailable_fallback(
            {
                "action": "wait",
                "reasoning": "Error occurred: transport failure",
                "goal_update": None,
                "recorded_in_context": False,
                "decision_source": "ai_error",
                "decision_path": "ai",
            },
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

        self.assertEqual(decision["action"], "wait")
        self.assertEqual(decision["decision_source"], "ai_error")
        self.assertEqual(decision["decision_path"], "ai")

    def test_rewrite_wait_prefers_field_fallback_when_text_flag_looks_stale(self):
        agent = object.__new__(PokemonAIAgent)
        agent._get_local_safe_exploration_decision = lambda *_args, **_kwargs: {
            "action": "up",
            "reasoning": "Use local navigation hints to keep exploring via up",
            "goal_update": None,
            "recorded_in_context": False,
        }
        agent._get_blocked_field_interaction_decision = lambda *_args, **_kwargs: None
        agent._build_passive_progress_decision = lambda *_args, **_kwargs: None
        agent._choose_recovery_move = lambda *_args, **_kwargs: "left"

        decision = agent._rewrite_wait_decision(
            {
                "action": "wait",
                "reasoning": "API cooldown active",
                "goal_update": None,
                "recorded_in_context": False,
                "decision_source": "ai_cooldown",
                "screen_type": "overworld",
            },
            {
                "memory": {
                    "ui": {"text_box_active": True, "menu_active": False},
                    "in_battle": False,
                }
            },
            "overworld",
        )

        self.assertEqual(decision["action"], "up")
        self.assertEqual(decision["decision_source"], "wait_rewrite_ai_cooldown")
        self.assertIn("Original WAIT reasoning: API cooldown active", decision["reasoning"])

    def test_rewrite_wait_uses_known_exit_even_when_navigation_lists_all_directions_blocked(self):
        agent = object.__new__(PokemonAIAgent)
        agent._temporarily_avoided_moves = {}
        agent._prune_temporarily_avoided_moves = lambda: None
        agent._get_blocked_field_interaction_decision = (
            PokemonAIAgent._get_blocked_field_interaction_decision.__get__(agent, PokemonAIAgent)
        )
        agent._get_local_safe_exploration_decision = (
            PokemonAIAgent._get_local_safe_exploration_decision.__get__(agent, PokemonAIAgent)
        )
        agent._get_retryable_field_directions = (
            PokemonAIAgent._get_retryable_field_directions.__get__(agent, PokemonAIAgent)
        )
        agent._build_passive_progress_decision = lambda *_args, **_kwargs: None
        agent._choose_recovery_move = lambda *_args, **_kwargs: "up"

        decision = agent._rewrite_wait_decision(
            {
                "action": "wait",
                "reasoning": "API cooldown active for 1.0s after recent request failures",
                "goal_update": None,
                "recorded_in_context": False,
                "decision_source": "ai_cooldown",
                "screen_type": "overworld",
            },
            {
                "memory": {
                    "position": {"map_id": 0, "x": 8, "y": 2},
                    "ui": {"text_box_active": False, "menu_active": False},
                    "in_battle": False,
                },
                "navigation": {
                    "blocked_directions": ["up", "down", "left", "right"],
                    "adjacent_tiles": {
                        "up": {"status": "blocked_once", "target_is_warp": False, "step_triggers_warp": False},
                        "down": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                        "left": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                        "right": {"status": "known_exit", "target_is_warp": False, "step_triggers_warp": False},
                    },
                },
                "visual": {"navigation_hints": {"blocked_directions": []}},
                "exploration": {"nearby_unexplored": []},
            },
            "overworld",
        )

        self.assertEqual(decision["action"], "left")
        self.assertEqual(decision["decision_source"], "wait_rewrite_ai_cooldown")

    def test_rewrite_wait_keeps_dialogue_advance_inside_real_dialogue(self):
        agent = object.__new__(PokemonAIAgent)
        agent._get_local_safe_exploration_decision = lambda *_args, **_kwargs: {
            "action": "up",
            "reasoning": "Use local navigation hints to keep exploring via up",
            "goal_update": None,
            "recorded_in_context": False,
        }
        agent._get_blocked_field_interaction_decision = lambda *_args, **_kwargs: None
        agent._build_passive_progress_decision = lambda *_args, **_kwargs: None
        agent._choose_recovery_move = lambda *_args, **_kwargs: "left"

        decision = agent._rewrite_wait_decision(
            {
                "action": "wait",
                "reasoning": "API cooldown active",
                "goal_update": None,
                "recorded_in_context": False,
                "decision_source": "ai_cooldown",
                "screen_type": "dialogue",
            },
            {
                "memory": {
                    "ui": {"text_box_active": True, "menu_active": False},
                    "in_battle": False,
                }
            },
            "dialogue",
        )

        self.assertEqual(decision["action"], "a")
        self.assertEqual(decision["decision_source"], "wait_rewrite_ai_cooldown")

    def test_ai_full_control_keeps_main_model_field_wait_unchanged(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"decision.ai_full_control_mode": True})

        decision = agent._rewrite_wait_decision(
            {
                "action": "wait",
                "reasoning": "Need another frame to inspect the room",
                "goal_update": None,
                "recorded_in_context": False,
                "decision_source": "ai",
                "screen_type": "overworld",
            },
            {
                "memory": {
                    "ui": {"text_box_active": False, "menu_active": False},
                    "in_battle": False,
                }
            },
            "overworld",
        )

        self.assertEqual(decision["action"], "wait")
        self.assertEqual(decision["decision_source"], "ai")

    def test_ai_full_control_still_rewrites_field_wait_when_ai_is_unavailable(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"decision.ai_full_control_mode": True})
        agent._get_local_safe_exploration_decision = lambda *_args, **_kwargs: {
            "action": "up",
            "reasoning": "Use local navigation hints to keep exploring via up",
            "goal_update": None,
            "recorded_in_context": False,
        }
        agent._get_blocked_field_interaction_decision = lambda *_args, **_kwargs: None
        agent._build_passive_progress_decision = lambda *_args, **_kwargs: None
        agent._choose_recovery_move = lambda *_args, **_kwargs: "left"

        decision = agent._rewrite_wait_decision(
            {
                "action": "wait",
                "reasoning": "API cooldown active",
                "goal_update": None,
                "recorded_in_context": False,
                "decision_source": "ai_cooldown",
                "screen_type": "overworld",
            },
            {
                "memory": {
                    "ui": {"text_box_active": False, "menu_active": False},
                    "in_battle": False,
                }
            },
            "overworld",
        )

        self.assertEqual(decision["action"], "up")
        self.assertEqual(decision["decision_source"], "wait_rewrite_ai_cooldown")

    def test_ai_unavailable_fallback_prefers_battle_progress_over_menu_close(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({})

        decision = agent._get_ai_unavailable_fallback_decision(
            {
                "memory": {
                    "in_battle": False,
                    "ui": {"menu_active": True, "text_box_active": False},
                    "battle": {"enemy_current_hp": 14},
                },
                "battle_summary": {"phase": "battle_in_progress"},
            },
            "battle",
        )

        self.assertEqual(decision["action"], "a")
        self.assertEqual(decision["decision_source"], "api_unavailable_battle_fallback")
        self.assertEqual(decision["decision_path"], "fallback")

    def test_rewrite_wait_prefers_battle_progress_when_battle_screen_has_menu_overlay(self):
        agent = object.__new__(PokemonAIAgent)
        agent._get_safe_battle_progress_decision = (
            PokemonAIAgent._get_safe_battle_progress_decision.__get__(agent, PokemonAIAgent)
        )
        agent._get_local_safe_exploration_decision = lambda *_args, **_kwargs: None
        agent._get_blocked_field_interaction_decision = lambda *_args, **_kwargs: None
        agent._build_passive_progress_decision = lambda *_args, **_kwargs: None
        agent._choose_recovery_move = lambda *_args, **_kwargs: "left"

        decision = agent._rewrite_wait_decision(
            {
                "action": "wait",
                "reasoning": "API cooldown active for 26.9s after recent request failures",
                "goal_update": None,
                "recorded_in_context": False,
                "decision_source": "ai_cooldown",
                "screen_type": "battle",
            },
            {
                "memory": {
                    "in_battle": False,
                    "ui": {"text_box_active": False, "menu_active": True},
                    "battle": {"enemy_current_hp": 14},
                },
                "battle_summary": {"phase": "battle_in_progress"},
            },
            "battle",
        )

        self.assertEqual(decision["action"], "a")
        self.assertEqual(decision["decision_source"], "wait_rewrite_ai_cooldown")
        self.assertIn("Original WAIT reasoning: API cooldown active", decision["reasoning"])

    def test_rewrite_wait_closes_post_faint_battle_menu_with_b(self):
        agent = object.__new__(PokemonAIAgent)
        agent._get_safe_battle_progress_decision = (
            PokemonAIAgent._get_safe_battle_progress_decision.__get__(agent, PokemonAIAgent)
        )
        agent._get_local_safe_exploration_decision = lambda *_args, **_kwargs: None
        agent._get_blocked_field_interaction_decision = lambda *_args, **_kwargs: None
        agent._build_passive_progress_decision = lambda *_args, **_kwargs: None
        agent._choose_recovery_move = lambda *_args, **_kwargs: "left"

        decision = agent._rewrite_wait_decision(
            {
                "action": "wait",
                "reasoning": "API cooldown active",
                "goal_update": None,
                "recorded_in_context": False,
                "decision_source": "ai_cooldown",
                "screen_type": "battle",
            },
            {
                "memory": {
                    "in_battle": True,
                    "ui": {"text_box_active": False, "menu_active": True},
                    "battle": {"enemy_current_hp": 0},
                },
                "battle_summary": {"phase": "battle_in_progress"},
            },
            "battle",
        )

        self.assertEqual(decision["action"], "b")
        self.assertEqual(decision["decision_source"], "wait_rewrite_ai_cooldown")

    def test_llm_primary_cached_ai_plan_consumes_next_step_on_field(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "decision.llm_primary_mode": True,
                "decision.llm_primary_action_plan_enabled": True,
            }
        )
        agent._planned_actions = ["up", "left"]
        agent._planned_target = None
        agent._planned_reasoning = "AI plan: continue moving"

        decision = agent._get_cached_ai_plan_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "in_battle": False,
                    "ui": {"text_box_active": False, "menu_active": False},
                },
                "deltas": {"movement_stall_turns": 0},
            },
            "overworld",
        )

        self.assertEqual(decision["action"], "up")
        self.assertEqual(agent._planned_actions, ["left"])

    def test_llm_primary_cached_ai_plan_clears_when_ui_interrupts(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "decision.llm_primary_mode": True,
                "decision.llm_primary_action_plan_enabled": True,
            }
        )
        agent._planned_actions = ["up", "left"]
        agent._planned_target = None
        agent._planned_reasoning = "AI plan: continue moving"

        decision = agent._get_cached_ai_plan_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "in_battle": False,
                    "ui": {"text_box_active": True, "menu_active": False},
                },
                "deltas": {"movement_stall_turns": 0},
            },
            "dialogue",
        )

        self.assertIsNone(decision)
        self.assertEqual(agent._planned_actions, [])

    def test_llm_primary_cached_ai_plan_clears_after_recent_scene_change(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "decision.llm_primary_mode": True,
                "decision.llm_primary_action_plan_enabled": True,
            }
        )
        agent._planned_actions = ["right", "up"]
        agent._planned_target = None
        agent._planned_reasoning = "AI plan: continue moving"
        agent.main_agent = type(
            "_MainAgentContextStub",
            (),
            {
                "context": type(
                    "_ContextStub",
                    (),
                    {
                        "recent_turns": [
                            type(
                                "_TurnStub",
                                (),
                                {
                                    "decision_source": "ai",
                                    "result": "After right: moved from (4,10) to (4,11); screen changed from indoor to overworld",
                                },
                            )()
                        ]
                    },
                )()
            },
        )()

        decision = agent._get_cached_ai_plan_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "in_battle": False,
                    "ui": {"text_box_active": False, "menu_active": False},
                },
                "deltas": {"movement_stall_turns": 0},
            },
            "overworld",
        )

        self.assertIsNone(decision)
        self.assertEqual(agent._planned_actions, [])

    def test_llm_primary_cached_ai_plan_clears_after_failed_cached_step(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "decision.llm_primary_mode": True,
                "decision.llm_primary_action_plan_enabled": True,
            }
        )
        agent._planned_actions = ["right", "up"]
        agent._planned_target = None
        agent._planned_reasoning = "AI plan: continue moving"
        agent.main_agent = type(
            "_MainAgentContextStub",
            (),
            {
                "context": type(
                    "_ContextStub",
                    (),
                    {
                        "recent_turns": [
                            type(
                                "_TurnStub",
                                (),
                                {
                                    "decision_source": "cached_ai_plan",
                                    "result": "After right: position did not change",
                                },
                            )()
                        ]
                    },
                )()
            },
        )()

        decision = agent._get_cached_ai_plan_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "in_battle": False,
                    "ui": {"text_box_active": False, "menu_active": False},
                },
                "deltas": {"movement_stall_turns": 0},
            },
            "overworld",
        )

        self.assertIsNone(decision)
        self.assertEqual(agent._planned_actions, [])

    def test_llm_primary_cached_ai_plan_clears_on_heavily_revisited_tile(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "decision.llm_primary_mode": True,
                "decision.llm_primary_action_plan_enabled": True,
            }
        )
        agent._planned_actions = ["right", "up"]
        agent._planned_target = None
        agent._planned_reasoning = "AI plan: continue moving"

        decision = agent._get_cached_ai_plan_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "in_battle": False,
                    "ui": {"text_box_active": False, "menu_active": False},
                    "position": {"map_id": 1, "x": 10, "y": 4},
                },
                "navigation": {
                    "current_visit_count": 6,
                },
                "deltas": {"movement_stall_turns": 0},
            },
            "overworld",
        )

        self.assertIsNone(decision)
        self.assertEqual(agent._planned_actions, [])

    def test_llm_primary_cached_ai_plan_clears_when_live_navigation_disagrees(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "decision.llm_primary_mode": True,
                "decision.llm_primary_action_plan_enabled": True,
            }
        )
        agent._planned_actions = ["up", "left"]
        agent._planned_target = None
        agent._planned_reasoning = "AI plan: continue moving"
        agent._temporarily_avoided_moves = {}

        decision = agent._get_cached_ai_plan_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "in_battle": False,
                    "ui": {"text_box_active": False, "menu_active": False},
                    "position": {"map_id": 1, "x": 10, "y": 4},
                },
                "navigation": {
                    "current_visit_count": 1,
                    "blocked_directions": ["up"],
                    "nearest_frontier": {
                        "target": (10, 4),
                        "unknown_directions": ["left"],
                        "path": [],
                    },
                },
                "deltas": {"movement_stall_turns": 0},
                "visual": {"navigation_hints": {}},
            },
            "overworld",
        )

        self.assertIsNone(decision)
        self.assertEqual(agent._planned_actions, [])

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

    def test_choose_frontier_direction_prefers_guided_escape_direction(self):
        agent = object.__new__(PokemonAIAgent)
        agent._last_action = None
        agent._is_temporarily_avoided_move = lambda *_args, **_kwargs: False

        direction = agent._choose_frontier_direction(
            {
                "memory": {"position": {"map_id": 0, "x": 12, "y": 11}},
                "navigation": {
                    "blocked_directions": [],
                    "frontier_guidance": {
                        "prefer_leave_current_frontier": True,
                        "recommended_direction": "left",
                        "discouraged_directions": ["up", "right"],
                    },
                },
                "visual": {
                    "navigation_hints": {
                        "blocked_directions": [],
                        "walkable_directions": ["up", "left", "right"],
                    }
                },
                "deltas": {"position_changed": False},
            },
            ["up", "left", "right"],
        )

        self.assertEqual(direction, "left")

    def test_choose_frontier_direction_avoids_adjacent_warp_tile(self):
        agent = object.__new__(PokemonAIAgent)
        agent._last_action = None
        agent._is_temporarily_avoided_move = lambda *_args, **_kwargs: False

        direction = agent._choose_frontier_direction(
            {
                "memory": {"position": {"map_id": 0, "x": 12, "y": 11}},
                "navigation": {
                    "blocked_directions": [],
                    "frontier_guidance": {},
                    "adjacent_tiles": {
                        "down": {"target_is_warp": True, "step_triggers_warp": False},
                        "right": {"target_is_warp": False, "step_triggers_warp": False},
                    },
                },
                "visual": {
                    "navigation_hints": {
                        "blocked_directions": [],
                        "walkable_directions": ["down", "right"],
                    }
                },
                "deltas": {"position_changed": False},
            },
            ["down", "right"],
        )

        self.assertEqual(direction, "right")

    def test_post_warp_reentry_guard_waits_for_doorway_auto_step(self):
        agent = object.__new__(PokemonAIAgent)
        agent._last_observed_state = {
            "memory": {"position": {"map_id": 40, "x": 4, "y": 11}}
        }
        agent._is_temporarily_avoided_move = lambda *_args, **_kwargs: False

        decision = agent._get_post_warp_reentry_guard_decision(
            {
                "memory": {"position": {"map_id": 0, "x": 12, "y": 11}, "in_battle": False},
                "navigation": {
                    "blocked_directions": [],
                    "warp_cautions": [
                        {
                            "direction": "down",
                            "target": {"x": 12, "y": 12},
                            "destination": {"map_id": 40, "x": 12, "y": 11},
                        }
                    ],
                    "adjacent_tiles": {
                        "up": {"status": "frontier", "target_is_warp": False},
                        "down": {"status": "adjacent_explored", "target_is_warp": True},
                        "left": {"status": "frontier", "target_is_warp": False},
                        "right": {"status": "frontier", "target_is_warp": False},
                    },
                    "frontier_guidance": {},
                },
                "visual": {"navigation_hints": {"blocked_directions": [], "walkable_directions": []}},
            },
            "unknown",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(decision["action"], "wait")
        self.assertEqual(decision["decision_source"], "post_warp_reentry_guard")

    def test_recent_warp_buffer_guard_blocks_reverse_reentry_action(self):
        agent = object.__new__(PokemonAIAgent)
        agent.turn_count = 50
        agent._recent_warp_exit = {
            "map_id": 0,
            "anchor": (12, 11),
            "blocked_action": "up",
            "source_map": 40,
            "expires_turn": 54,
            "radius": 2,
        }
        agent._choose_post_warp_escape_direction = lambda state, guarded: (
            "right" if guarded == ["up"] else None
        )

        decision = agent._get_recent_warp_buffer_guard_decision(
            {
                "memory": {"position": {"map_id": 0, "x": 12, "y": 12}, "in_battle": False},
                "navigation": {},
            },
            "overworld",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(decision["action"], "right")
        self.assertEqual(decision["decision_source"], "recent_warp_buffer_guard")

    def test_update_recent_warp_exit_guard_stores_reverse_action_after_transition(self):
        agent = object.__new__(PokemonAIAgent)
        agent.turn_count = 80
        agent.config = _ConfigStub(
            {
                "navigation.recent_warp_guard_turns": 4,
                "navigation.recent_warp_guard_radius": 2,
            }
        )
        agent._recent_warp_exit = None

        agent._update_recent_warp_exit_guard(
            {"memory": {"position": {"map_id": 40, "x": 4, "y": 11}}},
            {"memory": {"position": {"map_id": 0, "x": 12, "y": 11}}},
            "down",
        )

        self.assertEqual(
            agent._recent_warp_exit,
            {
                "map_id": 0,
                "anchor": (12, 11),
                "blocked_action": "up",
                "source_map": 40,
                "expires_turn": 84,
                "radius": 2,
            },
        )

    def test_update_recent_warp_exit_guard_records_warp_trigger_action(self):
        agent = object.__new__(PokemonAIAgent)
        agent.turn_count = 80
        agent.config = _ConfigStub(
            {
                "navigation.recent_warp_guard_turns": 4,
                "navigation.recent_warp_guard_radius": 2,
            }
        )
        agent._recent_warp_exit = None
        recorded = []
        agent.map_memory = SimpleNamespace(
            record_warp_trigger_action=lambda *args: recorded.append(args)
        )

        agent._update_recent_warp_exit_guard(
            {"memory": {"position": {"map_id": 40, "x": 4, "y": 11}}},
            {"memory": {"position": {"map_id": 0, "x": 12, "y": 11}}},
            "down",
        )

        self.assertEqual(recorded, [(40, 4, 11, "down")])

    def test_choose_post_warp_escape_direction_prefers_safe_step_off_current_warp_tile(self):
        agent = object.__new__(PokemonAIAgent)
        agent._is_temporarily_avoided_move = lambda *_args, **_kwargs: False

        direction = agent._choose_post_warp_escape_direction(
            {
                "memory": {"position": {"map_id": 0, "x": 12, "y": 12}},
                "navigation": {
                    "blocked_directions": ["left"],
                    "current_tile_warp": {
                        "destination": {"map_id": 40, "x": 12, "y": 11},
                        "trigger_action": "right",
                    },
                    "adjacent_tiles": {
                        "up": {
                            "status": "frontier",
                            "target_is_warp": False,
                            "step_triggers_warp": False,
                        },
                        "down": {
                            "status": "frontier",
                            "target_is_warp": False,
                            "step_triggers_warp": False,
                        },
                        "left": {
                            "status": "adjacent_explored",
                            "target_is_warp": False,
                            "step_triggers_warp": False,
                        },
                        "right": {
                            "status": "warp_trigger",
                            "target_is_warp": False,
                            "step_triggers_warp": True,
                        },
                    },
                    "frontier_guidance": {},
                },
                "visual": {"navigation_hints": {"blocked_directions": [], "walkable_directions": []}},
            },
            [],
        )

        self.assertEqual(direction, "left")

    def test_choose_post_warp_escape_direction_retries_non_trigger_blocked_once_on_known_warp_tile(self):
        agent = object.__new__(PokemonAIAgent)
        agent._is_temporarily_avoided_move = lambda *_args, **_kwargs: False

        direction = agent._choose_post_warp_escape_direction(
            {
                "memory": {"position": {"map_id": 0, "x": 12, "y": 12}},
                "navigation": {
                    "blocked_directions": ["up"],
                    "current_tile_warp": {
                        "destination": {"map_id": 40, "x": 12, "y": 11},
                        "trigger_action": "right",
                    },
                    "adjacent_tiles": {
                        "up": {
                            "status": "blocked_once",
                            "target_is_warp": False,
                            "step_triggers_warp": False,
                        },
                        "down": {
                            "status": "confirmed_blocked",
                            "target_is_warp": False,
                            "step_triggers_warp": False,
                        },
                        "left": {
                            "status": "confirmed_blocked",
                            "target_is_warp": False,
                            "step_triggers_warp": False,
                        },
                        "right": {
                            "status": "warp_trigger",
                            "target_is_warp": False,
                            "step_triggers_warp": True,
                        },
                    },
                    "frontier_guidance": {},
                },
                "visual": {"navigation_hints": {"blocked_directions": [], "walkable_directions": []}},
            },
            [],
        )

        self.assertEqual(direction, "up")

    def test_navigation_plan_uses_guided_escape_direction_for_weak_current_frontier(self):
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
        agent._is_temporarily_avoided_move = lambda *_args, **_kwargs: False
        agent._clear_planned_actions = PokemonAIAgent._clear_planned_actions.__get__(agent, PokemonAIAgent)

        decision = agent._get_navigation_plan_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "badge_count": 0,
                    "in_battle": False,
                    "position": {"map_id": 0, "x": 12, "y": 12},
                },
                "navigation": {
                    "current_visit_count": 8,
                    "blocked_directions": ["down"],
                    "nearest_frontier": {
                        "target": (12, 12),
                        "path": [],
                        "unknown_directions": ["right"],
                        "local_visit_pressure": 15,
                        "novelty_label": "low",
                    },
                    "adjacent_tiles": {
                        "up": {"status": "adjacent_explored", "target_is_warp": False},
                        "left": {"status": "adjacent_explored", "target_is_warp": False},
                        "right": {"status": "blocked_once", "target_is_warp": False},
                        "down": {"status": "confirmed_blocked", "target_is_warp": False},
                    },
                    "frontier_guidance": {
                        "prefer_leave_current_frontier": True,
                        "escape_direction": "left",
                        "summary": "Current tile is a weaker local frontier; leave it toward the stronger frontier.",
                    },
                },
                "deltas": {"movement_stall_turns": 1},
                "movement_pattern": {
                    "micro_loop_warning": True,
                },
                "visual": {"navigation_hints": {"blocked_directions": []}},
            },
            "overworld",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(decision["action"], "left")
        self.assertIn("weaker local frontier", decision["reasoning"])

    def test_navigation_plan_steps_off_current_warp_source_before_frontier_probe(self):
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
        agent._is_temporarily_avoided_move = lambda *_args, **_kwargs: False
        agent._clear_planned_actions = PokemonAIAgent._clear_planned_actions.__get__(agent, PokemonAIAgent)

        decision = agent._get_navigation_plan_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "badge_count": 0,
                    "in_battle": False,
                    "position": {"map_id": 0, "x": 12, "y": 12},
                },
                "navigation": {
                    "current_visit_count": 5,
                    "blocked_directions": ["left"],
                    "nearest_frontier": {
                        "target": (12, 12),
                        "path": [],
                        "unknown_directions": ["up", "right"],
                        "local_visit_pressure": 8,
                        "novelty_label": "medium",
                    },
                    "adjacent_tiles": {
                        "up": {
                            "status": "frontier",
                            "target_is_warp": False,
                            "step_triggers_warp": False,
                        },
                        "down": {
                            "status": "frontier",
                            "target_is_warp": False,
                            "step_triggers_warp": False,
                        },
                        "left": {
                            "status": "adjacent_explored",
                            "target_is_warp": False,
                            "step_triggers_warp": False,
                        },
                        "right": {
                            "status": "warp_trigger",
                            "target_is_warp": False,
                            "step_triggers_warp": True,
                        },
                    },
                    "current_tile_warp": {
                        "destination": {"map_id": 40, "x": 12, "y": 11},
                        "trigger_action": "right",
                    },
                    "frontier_guidance": {},
                },
                "deltas": {"movement_stall_turns": 1},
                "movement_pattern": {
                    "micro_loop_warning": False,
                },
                "visual": {"navigation_hints": {"blocked_directions": []}},
            },
            "overworld",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(decision["action"], "left")
        self.assertIn("known warp source", decision["reasoning"])

    def test_navigation_plan_abstains_on_current_warp_source_without_confirmed_step_off(self):
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
        agent._is_temporarily_avoided_move = lambda *_args, **_kwargs: False
        agent._clear_planned_actions = PokemonAIAgent._clear_planned_actions.__get__(agent, PokemonAIAgent)

        decision = agent._get_navigation_plan_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {
                    "badge_count": 0,
                    "in_battle": False,
                    "position": {"map_id": 0, "x": 12, "y": 12},
                },
                "navigation": {
                    "current_visit_count": 5,
                    "blocked_directions": [],
                    "current_tile_warp": {
                        "destination": {"map_id": 40, "x": 12, "y": 11},
                    },
                    "nearest_frontier": {
                        "target": (12, 12),
                        "path": [],
                        "unknown_directions": ["up", "down", "right"],
                        "local_visit_pressure": 8,
                        "novelty_label": "medium",
                    },
                    "adjacent_tiles": {
                        "up": {"status": "frontier", "target_is_warp": False},
                        "down": {"status": "frontier", "target_is_warp": False},
                        "left": {"status": "confirmed_blocked", "target_is_warp": False},
                        "right": {"status": "frontier", "target_is_warp": False},
                    },
                    "frontier_guidance": {},
                },
                "deltas": {"movement_stall_turns": 1},
                "movement_pattern": {
                    "micro_loop_warning": False,
                },
                "visual": {"navigation_hints": {"blocked_directions": []}},
            },
            "overworld",
        )

        self.assertIsNone(decision)

    def test_guided_navigation_escape_uses_navigation_plan_when_frontier_is_weak(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({})
        recorded = []

        agent._get_navigation_plan_decision = (
            lambda current_state, screen_type, force=False: recorded.append(
                (screen_type, force, current_state["navigation"]["current_visit_count"])
            )
            or {
                "action": "down",
                "reasoning": "Planner: leave the weaker local frontier via down.",
                "goal_update": None,
                "recorded_in_context": False,
            }
        )

        decision = agent._get_guided_navigation_escape_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {"in_battle": False},
                "navigation": {
                    "current_visit_count": 4,
                    "blocked_directions": ["left"],
                    "frontier_guidance": {
                        "prefer_leave_current_frontier": True,
                    },
                    "warp_cautions": [],
                },
                "movement_pattern": {"micro_loop_warning": False},
                "deltas": {"movement_stall_turns": 2},
            },
            "overworld",
        )

        self.assertEqual(recorded, [("overworld", True, 4)])
        self.assertEqual(decision["action"], "down")
        self.assertEqual(decision["decision_source"], "guided_navigation_escape")
        self.assertEqual(decision["decision_path"], "tool")
        self.assertIn("risky warp fringe", decision["reasoning"])

    def test_guided_navigation_escape_skips_mild_frontier_pressure(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({})
        agent._get_navigation_plan_decision = lambda *_args, **_kwargs: {
            "action": "down",
            "reasoning": "Planner: leave the weaker local frontier via down.",
            "goal_update": None,
            "recorded_in_context": False,
        }

        decision = agent._get_guided_navigation_escape_decision(
            {
                "pre_world": False,
                "pre_starter_script": False,
                "memory": {"in_battle": False},
                "navigation": {
                    "current_visit_count": 4,
                    "blocked_directions": ["left"],
                    "frontier_guidance": {
                        "prefer_leave_current_frontier": True,
                    },
                    "warp_cautions": [],
                },
                "movement_pattern": {"micro_loop_warning": False},
                "deltas": {"movement_stall_turns": 1},
            },
            "overworld",
        )

        self.assertIsNone(decision)

    def test_llm_primary_fixed_route_state_skips_stuck_logic(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"decision.llm_primary_mode": True})
        agent.post_battle_intro_route = PostBattleIntroRouteController()

        self.assertTrue(
            agent._is_early_fixed_route_state(
                {
                    "memory": {
                        "position": {"map_id": 40, "x": 4, "y": 8},
                        "badge_count": 0,
                        "money": 3175,
                        "item_count": 0,
                        "in_battle": False,
                        "ui": {"text_box_active": False, "menu_active": False},
                        "party": [{"level": 6, "moves": [{"move_id": 10}, {"move_id": 45}]}],
                    }
                }
            )
        )

    def test_ai_full_control_mode_disables_fixed_route_state_shortcut(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "decision.llm_primary_mode": True,
                "decision.ai_full_control_mode": True,
            }
        )
        agent.post_battle_intro_route = PostBattleIntroRouteController()

        self.assertFalse(
            agent._is_early_fixed_route_state(
                {
                    "memory": {
                        "position": {"map_id": 40, "x": 4, "y": 8},
                        "badge_count": 0,
                        "money": 3175,
                        "item_count": 0,
                        "in_battle": False,
                        "ui": {"text_box_active": False, "menu_active": False},
                        "party": [{"level": 6, "moves": [{"move_id": 10}, {"move_id": 45}]}],
                    }
                }
            )
        )

    def test_fixed_route_state_uses_viridian_parcel_controller_during_return_arc(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({})
        agent.viridian_parcel_controller = ViridianParcelController()

        self.assertTrue(
            agent._is_early_fixed_route_state(
                {
                    "memory": {
                        "position": {"map_id": 0, "x": 16, "y": 8},
                        "badge_count": 0,
                        "money": 3175,
                        "item_count": 1,
                        "in_battle": False,
                        "ui": {"text_box_active": False, "menu_active": False},
                        "party": [{"level": 7}],
                        "events": {"got_oaks_parcel": True},
                    }
                }
            )
        )

    def test_fixed_route_state_uses_post_pokedex_departure_controller_after_scene(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({})
        agent.post_pokedex_departure_controller = PostPokedexDepartureController()

        self.assertTrue(
            agent._is_early_fixed_route_state(
                {
                    "memory": {
                        "position": {"map_id": 40, "x": 5, "y": 3},
                        "badge_count": 0,
                        "money": 3175,
                        "item_count": 0,
                        "in_battle": False,
                        "ui": {"text_box_active": False, "menu_active": False},
                        "party": [{"level": 6}],
                        "events": {"got_pokedex": True, "oak_got_parcel": True},
                    }
                }
            )
        )

    def test_fixed_route_state_drops_post_pokedex_states_outside_guided_window(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({})
        agent.post_pokedex_departure_controller = PostPokedexDepartureController()

        self.assertFalse(
            agent._is_early_fixed_route_state(
                {
                    "memory": {
                        "position": {"map_id": 40, "x": 8, "y": 11},
                        "badge_count": 0,
                        "money": 3175,
                        "item_count": 0,
                        "in_battle": False,
                        "ui": {"text_box_active": False, "menu_active": False},
                        "party": [{"level": 6}],
                        "events": {"got_pokedex": True, "oak_got_parcel": True},
                    }
                }
            )
        )

    def test_llm_primary_uses_precise_direction_for_tool_decisions(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"decision.llm_primary_mode": True})

        self.assertTrue(
            agent._should_use_precise_direction_execution(
                {"decision_source": "post_battle_intro_route"},
                "up",
            )
        )
        self.assertFalse(
            agent._should_use_precise_direction_execution(
                {"decision_source": "ai"},
                "up",
            )
        )

    def test_deterministic_turn_in_place_records_failed_move(self):
        agent = object.__new__(PokemonAIAgent)
        agent._last_observed_state = {
            "memory": {
                "position": {"map_id": 0, "x": 12, "y": 11},
                "direction": "down",
            }
        }
        agent._last_action = "up"
        agent._last_action_source = "post_warp_reentry_guard"
        agent._clear_planned_actions = lambda: None
        agent.map_memory = _MapMemoryRecordFailedMoveStub()
        recorded = []
        agent.main_agent = SimpleNamespace(record_action_outcome=lambda result: recorded.append(result))
        agent._summarize_action_outcome = lambda *_args, **_kwargs: "position did not change"
        agent._update_trigger_tile_memory = lambda *_args, **_kwargs: None

        agent._record_last_action_outcome(
            {
                "memory": {
                    "position": {"map_id": 0, "x": 12, "y": 11},
                    "direction": "up",
                    "ui": {"text_box_active": False},
                    "in_battle": False,
                }
            },
            "overworld",
        )

        self.assertEqual(recorded, ["position did not change"])
        self.assertEqual(agent.map_memory.calls, [(0, 12, 11, "up")])

    def test_guided_navigation_turn_in_place_records_failed_move(self):
        agent = object.__new__(PokemonAIAgent)
        agent._last_observed_state = {
            "memory": {
                "position": {"map_id": 0, "x": 11, "y": 12},
                "direction": "left",
            }
        }
        agent._last_action = "down"
        agent._last_action_source = "guided_navigation_escape"
        agent._clear_planned_actions = lambda: None
        agent.map_memory = _MapMemoryRecordFailedMoveStub()
        agent.main_agent = SimpleNamespace(record_action_outcome=lambda *_args, **_kwargs: None)
        agent._summarize_action_outcome = lambda *_args, **_kwargs: None
        agent._update_trigger_tile_memory = lambda *_args, **_kwargs: None
        agent._update_recent_warp_exit_guard = lambda *_args, **_kwargs: None

        agent._record_last_action_outcome(
            {
                "memory": {
                    "position": {"map_id": 0, "x": 11, "y": 12},
                    "direction": "down",
                    "ui": {"text_box_active": False},
                    "in_battle": False,
                }
            },
            "overworld",
        )

        self.assertEqual(agent.map_memory.calls, [(0, 11, 12, "down")])

    def test_wait_rewrite_turn_in_place_records_failed_move(self):
        agent = object.__new__(PokemonAIAgent)
        agent._last_observed_state = {
            "memory": {
                "position": {"map_id": 40, "x": 8, "y": 11},
                "direction": "left",
            }
        }
        agent._last_action = "down"
        agent._last_action_source = "wait_rewrite_ai_cooldown"
        agent._clear_planned_actions = lambda: None
        agent.map_memory = _MapMemoryRecordFailedMoveStub()
        agent.main_agent = SimpleNamespace(record_action_outcome=lambda *_args, **_kwargs: None)
        agent._summarize_action_outcome = lambda *_args, **_kwargs: None
        agent._update_trigger_tile_memory = lambda *_args, **_kwargs: None
        agent._update_recent_warp_exit_guard = lambda *_args, **_kwargs: None

        agent._record_last_action_outcome(
            {
                "memory": {
                    "position": {"map_id": 40, "x": 8, "y": 11},
                    "direction": "down",
                    "ui": {"text_box_active": False},
                    "in_battle": False,
                }
            },
            "indoor",
        )

        self.assertEqual(agent.map_memory.calls, [(40, 8, 11, "down")])

    def test_research_mode_stage_specs_drop_fixed_route_controllers(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"decision.research_mode": True})

        stage_names = [name for name, _ in agent._get_decision_stage_specs()]

        self.assertNotIn("oak_lab_starter", stage_names)
        self.assertNotIn("oak_lab_post_starter", stage_names)
        self.assertNotIn("oak_lab_rival_battle", stage_names)
        self.assertNotIn("post_battle_intro_route", stage_names)
        self.assertNotIn("post_pokedex_departure", stage_names)
        self.assertIn("known_ui", stage_names)
        self.assertIn("navigation_plan", stage_names)

    def test_llm_primary_stage_specs_keep_only_minimal_safety_stages(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"decision.llm_primary_mode": True})

        stage_names = [name for name, _ in agent._get_decision_stage_specs()]

        self.assertEqual(
            stage_names,
            [
                "bootstrap",
                "minimal_known_ui",
                "post_warp_reentry_guard",
                "early_battle",
                "post_battle_intro_route",
                "viridian_parcel",
                "post_pokedex_departure",
                "recent_warp_buffer_guard",
                "guided_navigation_escape",
                "cached_ai_plan",
                "stable_ui_recovery",
                "menu_auto_close",
                "text_entry_api_cooldown",
            ],
        )

    def test_ai_full_control_stage_specs_drop_scripted_story_and_battle_owners(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub(
            {
                "decision.llm_primary_mode": True,
                "decision.ai_full_control_mode": True,
            }
        )

        stage_names = [name for name, _ in agent._get_decision_stage_specs()]

        self.assertEqual(
            stage_names,
            [
                "bootstrap",
                "minimal_known_ui",
                "post_warp_reentry_guard",
                "recent_warp_buffer_guard",
                "guided_navigation_escape",
                "cached_ai_plan",
                "stable_ui_recovery",
                "menu_auto_close",
                "text_entry_api_cooldown",
            ],
        )

    def test_early_battle_stage_uses_extended_button_settle(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"actions.early_battle_button_settle_frames": 36})

        override = agent._get_action_settle_override(
            {"decision_source": "early_battle"},
            "a",
        )

        self.assertEqual(override, 36)

    def test_ai_led_battle_text_uses_extended_button_settle(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"actions.ai_battle_text_button_settle_frames": 24})

        override = agent._get_action_settle_override(
            {"decision_source": "ai"},
            "a",
            current_state={
                "memory": {
                    "in_battle": True,
                    "ui": {"text_box_active": True, "menu_active": False},
                },
                "battle_summary": {"phase": "battle_in_progress"},
            },
        )

        self.assertEqual(override, 24)

    def test_ai_led_battle_menu_keeps_default_settle_window(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({"actions.ai_battle_text_button_settle_frames": 24})

        override = agent._get_action_settle_override(
            {"decision_source": "ai"},
            "a",
            current_state={
                "memory": {
                    "in_battle": True,
                    "ui": {"text_box_active": False, "menu_active": True},
                },
                "battle_summary": {"phase": "battle_in_progress"},
            },
        )

        self.assertIsNone(override)

    def test_default_stage_specs_keep_fixed_route_controllers(self):
        agent = object.__new__(PokemonAIAgent)
        agent.config = _ConfigStub({})

        stage_names = [name for name, _ in agent._get_decision_stage_specs()]

        self.assertIn("oak_lab_starter", stage_names)
        self.assertIn("oak_lab_post_starter", stage_names)
        self.assertIn("oak_lab_rival_battle", stage_names)
        self.assertIn("post_battle_intro_route", stage_names)
        self.assertIn("viridian_parcel", stage_names)
        self.assertIn("post_pokedex_departure", stage_names)


if __name__ == "__main__":
    unittest.main()
