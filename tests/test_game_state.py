import unittest

from src.state.game_state import GameState


class GameStateBattleSummaryTests(unittest.TestCase):
    def _make_state(self):
        state = object.__new__(GameState)
        state._last_memory_state = None
        state._battle_turns = 0
        state._battle_stall_turns = 0
        return state

    def test_battle_summary_marks_entered_trainer_battle(self):
        state = self._make_state()
        state._last_memory_state = {
            "in_battle": False,
            "battle": {"battle_type": "none"},
        }

        summary = state._analyze_battle_state(
            {
                "in_battle": True,
                "battle": {
                    "battle_type": "trainer",
                    "enemy_species": "Pidgey",
                    "enemy_level": 5,
                    "enemy_current_hp": 20,
                },
                "party": [
                    {
                        "species": "Charmander",
                        "level": 7,
                        "current_hp": 12,
                        "max_hp": 24,
                    }
                ],
                "ui": {"text_box_active": False},
            }
        )

        self.assertEqual(summary["phase"], "entered_battle")
        self.assertEqual(summary["encounter_type"], "trainer")
        self.assertEqual(summary["battle_turns"], 1)
        self.assertEqual(summary["lead_pokemon"]["hp_percent"], 50.0)
        self.assertIn("trainer battle", summary["focus_hint"].lower())

    def test_battle_summary_detects_battle_stall(self):
        state = self._make_state()
        state._battle_turns = 3
        state._battle_stall_turns = 2
        state._last_memory_state = {
            "in_battle": True,
            "battle": {
                "battle_type": "wild",
                "enemy_species": "Rattata",
                "enemy_level": 4,
                "enemy_current_hp": 18,
            },
        }

        summary = state._analyze_battle_state(
            {
                "in_battle": True,
                "battle": {
                    "battle_type": "wild",
                    "enemy_species": "Rattata",
                    "enemy_level": 4,
                    "enemy_current_hp": 18,
                },
                "party": [
                    {
                        "species": "Charmander",
                        "level": 7,
                        "current_hp": 12,
                        "max_hp": 24,
                    }
                ],
                "ui": {"text_box_active": False},
            }
        )

        self.assertEqual(summary["phase"], "battle_in_progress")
        self.assertEqual(summary["battle_turns"], 4)
        self.assertEqual(summary["battle_stall_turns"], 3)
        self.assertFalse(summary["enemy_hp_changed"])
        self.assertIn("stalled", summary["focus_hint"].lower())

    def test_battle_summary_marks_post_battle_dialogue(self):
        state = self._make_state()
        state._battle_turns = 4
        state._battle_stall_turns = 1
        state._last_memory_state = {
            "in_battle": True,
            "battle": {
                "battle_type": "trainer",
                "enemy_species": "Squirtle",
                "enemy_level": 5,
                "enemy_current_hp": 0,
            },
        }

        summary = state._analyze_battle_state(
            {
                "in_battle": False,
                "battle": {
                    "battle_type": "none",
                    "enemy_species": None,
                    "enemy_level": None,
                    "enemy_current_hp": None,
                },
                "party": [
                    {
                        "species": "Charmander",
                        "level": 8,
                        "current_hp": 9,
                        "max_hp": 26,
                    }
                ],
                "ui": {"text_box_active": True},
            }
        )

        self.assertEqual(summary["phase"], "post_battle_dialogue")
        self.assertEqual(summary["encounter_type"], "trainer")
        self.assertEqual(summary["battle_turns"], 0)
        self.assertEqual(summary["battle_stall_turns"], 0)
        self.assertIn("finish the text", summary["focus_hint"].lower())

    def test_battle_guidance_prefers_fight_then_damaging_move(self):
        state = self._make_state()

        guidance = state._build_battle_guidance(
            {
                "in_battle": True,
                "battle": {
                    "battle_type": "wild",
                    "enemy_species": "Rattata",
                    "enemy_level": 3,
                    "enemy_current_hp": 18,
                },
                "party": [
                    {
                        "species": "Charmander",
                        "level": 6,
                        "current_hp": 21,
                        "max_hp": 21,
                        "moves": [
                            {"move_id": 10, "pp": 35},
                            {"move_id": 45, "pp": 40},
                        ],
                    }
                ],
                "ui": {"text_box_active": False, "menu_active": True},
            },
            {
                "phase": "battle_in_progress",
                "encounter_type": "wild",
                "lead_pokemon": {
                    "species": "Charmander",
                    "level": 6,
                    "current_hp": 21,
                    "max_hp": 21,
                    "hp_percent": 100.0,
                },
            },
        )

        self.assertEqual(guidance["phase"], "battle_in_progress")
        self.assertIn("choose FIGHT", guidance["summary"])
        self.assertIn("slot 1 (Scratch, PP 35)", guidance["move_cue"])
        self.assertIn("slot 2 (Growl)", guidance["move_cue"])

    def test_battle_guidance_marks_post_battle_dialogue(self):
        state = self._make_state()

        guidance = state._build_battle_guidance(
            {
                "in_battle": False,
                "battle": {
                    "battle_type": "wild",
                    "enemy_species": "Rattata",
                    "enemy_level": 3,
                    "enemy_current_hp": 0,
                },
                "party": [
                    {
                        "species": "Charmander",
                        "level": 6,
                        "current_hp": 18,
                        "max_hp": 21,
                        "moves": [
                            {"move_id": 10, "pp": 34},
                            {"move_id": 45, "pp": 40},
                        ],
                    }
                ],
                "ui": {"text_box_active": True, "menu_active": False},
            },
            {
                "phase": "post_battle_dialogue",
                "encounter_type": "wild",
                "lead_pokemon": {
                    "species": "Charmander",
                    "level": 6,
                    "current_hp": 18,
                    "max_hp": 21,
                    "hp_percent": 85.7,
                },
            },
        )

        self.assertEqual(guidance["phase"], "post_battle_dialogue")
        self.assertIn("Keep advancing the text with A", guidance["summary"])

    def test_text_representation_includes_adjacent_tile_occupancy(self):
        state = self._make_state()

        text = state.get_text_representation(
            {
                "turn": 7,
                "memory": {
                    "position": {"map_id": 40, "x": 5, "y": 3},
                    "direction": "up",
                    "badges": {},
                    "badge_count": 0,
                    "party": [
                        {
                            "species": "Charmander",
                            "level": 7,
                            "current_hp": 20,
                            "max_hp": 20,
                            "moves": [{"pp": 35}],
                        }
                    ],
                    "money": 3000,
                    "item_count": 1,
                    "in_battle": False,
                    "battle": {},
                    "ui": {"text_box_active": False, "menu_active": False},
                },
                "pre_world": False,
                "pre_starter_script": False,
                "phase_hint": "indoor",
                "visual": {
                    "screen_type": "indoor",
                    "description": "Oak Lab interior",
                    "local_analysis_enabled": True,
                    "navigation_hints": {
                        "available": True,
                        "blocked_directions": ["right"],
                        "unsafe_directions": ["down"],
                        "walkable_directions": ["up", "left"],
                    },
                },
                "exploration": {"nearby_unexplored": []},
                "map_memory": {
                    "exploration_percent": 10.0,
                    "explored_tiles": 2,
                    "total_tiles": 200,
                },
                "navigation": {
                    "current_visit_count": 3,
                    "known_exits": {"up": {"x": 5, "y": 2}},
                    "blocked_directions": ["right"],
                    "frontier_count": 2,
                    "nearest_frontier": None,
                    "frontier_candidates": [],
                    "warp_cautions": [
                        {
                            "direction": "down",
                            "target": {"x": 5, "y": 4},
                            "destination": {"map_id": 40, "x": 4, "y": 11},
                        }
                    ],
                    "current_tile_warp": {
                        "source": {"x": 5, "y": 3},
                        "destination": {"map_id": 40, "x": 4, "y": 11},
                        "trigger_action": "right",
                    },
                    "frontier_guidance": {
                        "prefer_leave_current_frontier": True,
                        "summary": (
                            "Current tile is a weaker local frontier. "
                            "A stronger frontier at (2, 3) scores 30.0; prefer left."
                        ),
                    },
                    "adjacent_tiles": {
                        "up": {
                            "status": "known_exit",
                            "target": {"x": 5, "y": 2},
                            "blocked_attempts": 0,
                            "target_visit_count": 2,
                            "target_is_warp": False,
                            "is_preferred_frontier_step": False,
                        },
                        "down": {
                            "status": "frontier",
                            "target": {"x": 5, "y": 4},
                            "blocked_attempts": 0,
                            "target_visit_count": 0,
                            "target_is_warp": False,
                            "is_preferred_frontier_step": True,
                        },
                        "left": {
                            "status": "adjacent_explored",
                            "target": {"x": 4, "y": 3},
                            "blocked_attempts": 0,
                            "target_visit_count": 1,
                            "target_is_warp": False,
                            "is_preferred_frontier_step": False,
                        },
                        "right": {
                            "status": "confirmed_blocked",
                            "target": {"x": 6, "y": 3},
                            "blocked_attempts": 2,
                            "target_visit_count": 0,
                            "target_is_warp": False,
                            "is_preferred_frontier_step": False,
                        },
                    },
                    "local_map": [],
                    "map_snapshot": {"available": False},
                },
                "deltas": {
                    "position_changed": False,
                    "money_delta": 0,
                    "battle_toggled": False,
                    "movement_stall_turns": 1,
                    "stuck_hint": "slight stall",
                },
                "movement_pattern": {"window_size": 0},
                "battle_summary": {"phase": "not_in_battle"},
            }
        )

        self.assertIn("Adjacent Tile Occupancy:", text)
        self.assertIn(
            "Immediate movement preference: up=known_exit, left=adjacent_explored",
            text,
        )
        self.assertIn(
            "Immediate movement cautions: down=warp+preferred_route, right=warp+confirmed_blocked",
            text,
        )
        self.assertIn("up: status=known_exit target=(5, 2) visits=2 vision=walkable", text)
        self.assertIn(
            "down: status=frontier target=(5, 4) preferred_frontier_step vision=unsafe",
            text,
        )
        self.assertIn(
            "right: status=confirmed_blocked target=(6, 3) blocked_attempts=2 vision=blocked",
            text,
        )
        self.assertIn(
            "Warp caution: down reaches known warp tile (5, 4) -> map 40 (4, 11); do not step on it unless you intentionally want to change maps.",
            text,
        )
        self.assertIn(
            "Current-tile warp caution: you are standing on known warp source (5, 3) -> map 40 (4, 11); the learned trigger action is right. Step off this tile before probing unknown directions.",
            text,
        )
        self.assertIn("Frontier caution: Current tile is a weaker local frontier.", text)

    def test_text_representation_marks_known_exit_as_currently_blocked(self):
        state = self._make_state()

        text = state.get_text_representation(
            {
                "turn": 15,
                "memory": {
                    "position": {"map_id": 40, "x": 9, "y": 9},
                    "direction": "up",
                    "badges": {},
                    "badge_count": 0,
                    "party": [
                        {
                            "species": "Charmander",
                            "level": 6,
                            "current_hp": 21,
                            "max_hp": 21,
                            "moves": [
                                {"move_id": 10, "pp": 35},
                                {"move_id": 45, "pp": 40},
                            ],
                        }
                    ],
                    "money": 3175,
                    "item_count": 0,
                    "in_battle": False,
                    "battle": {},
                    "ui": {"text_box_active": False, "menu_active": False},
                },
                "pre_world": False,
                "pre_starter_script": False,
                "phase_hint": "indoor",
                "visual": {
                    "screen_type": "indoor",
                    "description": "Oak Lab rival blocker",
                    "local_analysis_enabled": False,
                    "navigation_hints": {"available": False},
                },
                "story_guidance": None,
                "exploration": {"nearby_unexplored": []},
                "map_memory": {
                    "exploration_percent": 21.0,
                    "explored_tiles": 42,
                    "total_tiles": 200,
                },
                "navigation": {
                    "current_visit_count": 12,
                    "known_exits": {"up": {"x": 9, "y": 8}, "left": {"x": 8, "y": 9}},
                    "blocked_directions": ["up", "down", "left", "right"],
                    "frontier_count": 4,
                    "nearest_frontier": None,
                    "frontier_candidates": [],
                    "warp_cautions": [],
                    "adjacent_tiles": {
                        "up": {
                            "status": "known_exit",
                            "target": {"x": 9, "y": 8},
                            "blocked_attempts": 2,
                            "target_visit_count": 4,
                            "target_is_warp": False,
                            "is_preferred_frontier_step": False,
                        },
                        "down": {
                            "status": "frontier",
                            "target": {"x": 9, "y": 10},
                            "blocked_attempts": 2,
                            "target_visit_count": 0,
                            "target_is_warp": False,
                            "is_preferred_frontier_step": False,
                        },
                        "left": {
                            "status": "adjacent_explored",
                            "target": {"x": 8, "y": 9},
                            "blocked_attempts": 1,
                            "target_visit_count": 2,
                            "target_is_warp": False,
                            "is_preferred_frontier_step": False,
                        },
                        "right": {
                            "status": "confirmed_blocked",
                            "target": {"x": 10, "y": 9},
                            "blocked_attempts": 2,
                            "target_visit_count": 0,
                            "target_is_warp": False,
                            "is_preferred_frontier_step": False,
                        },
                    },
                    "local_map": [],
                    "map_snapshot": {"available": False},
                },
                "deltas": {
                    "position_changed": False,
                    "money_delta": 0,
                    "battle_toggled": False,
                    "movement_stall_turns": 2,
                    "stuck_hint": "possibly stuck",
                },
                "movement_pattern": {"window_size": 0},
                "battle_summary": {"phase": "not_in_battle"},
            }
        )

        self.assertIn(
            (
                "Immediate movement cautions: up=known_exit_but_currently_blocked, "
                "down=frontier_but_currently_blocked, "
                "left=adjacent_explored_blocked_once, right=confirmed_blocked"
            ),
            text,
        )
        self.assertIn(
            "Interaction cue: a route that previously worked is currently blocked from this tile.",
            text,
        )

    def test_story_guidance_highlights_post_battle_pallet_north_exit(self):
        state = self._make_state()

        guidance = state._build_story_guidance(
            {
                "position": {"map_id": 0, "x": 11, "y": 2},
                "badge_count": 0,
                "money": 3175,
                "item_count": 0,
                "in_battle": False,
                "party": [{"level": 6}],
                "events": {},
            }
        )

        self.assertEqual(guidance["phase"], "post_battle_intro_route")
        self.assertEqual(guidance["priority"], "high")
        self.assertIn("prioritize UP", guidance["summary"])
        self.assertIn("Route 1", guidance["summary"])

    def test_story_guidance_highlights_oak_lab_exit_alignment(self):
        state = self._make_state()

        guidance = state._build_story_guidance(
            {
                "position": {"map_id": 40, "x": 6, "y": 11},
                "badge_count": 0,
                "money": 3175,
                "item_count": 0,
                "in_battle": False,
                "party": [{"level": 6}],
                "events": {},
            }
        )

        self.assertEqual(guidance["phase"], "post_battle_intro_route")
        self.assertEqual(guidance["priority"], "high")
        self.assertIn("x=4 or x=5", guidance["summary"])
        self.assertIn("move LEFT", guidance["summary"])

    def test_story_guidance_recovers_when_lab_exit_is_overshot_left(self):
        state = self._make_state()

        guidance = state._build_story_guidance(
            {
                "position": {"map_id": 40, "x": 2, "y": 11},
                "badge_count": 0,
                "money": 3175,
                "item_count": 0,
                "in_battle": False,
                "party": [{"level": 6}],
                "events": {},
            }
        )

        self.assertEqual(guidance["phase"], "post_battle_intro_route")
        self.assertEqual(guidance["priority"], "high")
        self.assertIn("move RIGHT", guidance["summary"])
        self.assertIn("press DOWN", guidance["summary"])

    def test_story_guidance_highlights_pallet_lab_frontage_west_route(self):
        state = self._make_state()

        guidance = state._build_story_guidance(
            {
                "position": {"map_id": 0, "x": 12, "y": 12},
                "badge_count": 0,
                "money": 3175,
                "item_count": 0,
                "in_battle": False,
                "party": [{"level": 6}],
                "events": {},
            }
        )

        self.assertEqual(guidance["phase"], "post_battle_intro_route")
        self.assertEqual(guidance["priority"], "high")
        self.assertIn("move LEFT", guidance["summary"])
        self.assertIn("x=9", guidance["summary"])

    def test_story_guidance_highlights_pallet_west_lane_climb(self):
        state = self._make_state()

        guidance = state._build_story_guidance(
            {
                "position": {"map_id": 0, "x": 9, "y": 8},
                "badge_count": 0,
                "money": 3175,
                "item_count": 0,
                "in_battle": False,
                "party": [{"level": 6}],
                "events": {},
            }
        )

        self.assertEqual(guidance["phase"], "post_battle_intro_route")
        self.assertEqual(guidance["priority"], "high")
        self.assertIn("keep moving UP", guidance["summary"])
        self.assertIn("x=9", guidance["summary"])

    def test_story_guidance_highlights_route1_left_corridor(self):
        state = self._make_state()

        guidance = state._build_story_guidance(
            {
                "position": {"map_id": 12, "x": 10, "y": 33},
                "badge_count": 0,
                "money": 3175,
                "item_count": 0,
                "in_battle": False,
                "party": [{"level": 7}],
                "events": {},
            }
        )

        self.assertEqual(guidance["phase"], "post_battle_intro_route")
        self.assertEqual(guidance["priority"], "high")
        self.assertIn("Route 1", guidance["summary"])
        self.assertIn("x=10", guidance["summary"])

    def test_story_guidance_highlights_viridian_mart_entry(self):
        state = self._make_state()

        guidance = state._build_story_guidance(
            {
                "position": {"map_id": 1, "x": 29, "y": 20},
                "badge_count": 0,
                "money": 3175,
                "item_count": 0,
                "in_battle": False,
                "party": [{"level": 7}],
                "events": {},
            }
        )

        self.assertEqual(guidance["phase"], "post_battle_intro_route")
        self.assertEqual(guidance["priority"], "high")
        self.assertIn("Viridian", guidance["summary"])
        self.assertIn("enter Viridian Mart", guidance["summary"])

    def test_story_guidance_highlights_parcel_return_route(self):
        state = self._make_state()

        guidance = state._build_story_guidance(
            {
                "position": {"map_id": 12, "x": 14, "y": 7},
                "badge_count": 0,
                "money": 3175,
                "item_count": 1,
                "in_battle": False,
                "party": [{"level": 7}],
                "events": {"got_oaks_parcel": True},
            }
        )

        self.assertEqual(guidance["phase"], "viridian_parcel_return")
        self.assertEqual(guidance["priority"], "high")
        self.assertIn("Route 1", guidance["summary"])
        self.assertIn("keep moving DOWN", guidance["summary"])

    def test_story_guidance_not_emitted_after_oak_got_parcel(self):
        state = self._make_state()

        guidance = state._build_story_guidance(
            {
                "position": {"map_id": 0, "x": 11, "y": 2},
                "badge_count": 0,
                "money": 3175,
                "item_count": 1,
                "in_battle": False,
                "party": [{"level": 7}],
                "events": {"oak_got_parcel": True},
            }
        )

        self.assertIsNone(guidance)

    def test_text_representation_includes_story_guidance(self):
        state = self._make_state()

        text = state.get_text_representation(
            {
                "turn": 12,
                "memory": {
                    "position": {"map_id": 0, "x": 11, "y": 2},
                    "direction": "up",
                    "badges": {},
                    "badge_count": 0,
                    "party": [
                        {
                            "species": "Charmander",
                            "level": 6,
                            "current_hp": 21,
                            "max_hp": 21,
                            "moves": [{"pp": 35}, {"pp": 40}],
                        }
                    ],
                    "money": 3175,
                    "item_count": 0,
                    "in_battle": False,
                    "battle": {},
                    "ui": {"text_box_active": False, "menu_active": False},
                },
                "pre_world": False,
                "pre_starter_script": False,
                "phase_hint": "overworld",
                "visual": {
                    "screen_type": "overworld",
                    "description": "Pallet Town north edge",
                    "local_analysis_enabled": False,
                    "navigation_hints": {"available": False},
                },
                "story_guidance": {
                    "phase": "post_battle_intro_route",
                    "priority": "high",
                    "summary": (
                        "Early-story objective: exit Pallet Town north into Route 1. "
                        "When aligned under the north grass opening, prioritize UP even if side-town frontier tiles look tempting."
                    ),
                },
                "exploration": {"nearby_unexplored": []},
                "map_memory": {
                    "exploration_percent": 20.0,
                    "explored_tiles": 10,
                    "total_tiles": 200,
                },
                "navigation": {
                    "current_visit_count": 3,
                    "known_exits": {},
                    "blocked_directions": [],
                    "frontier_count": 2,
                    "nearest_frontier": None,
                    "frontier_candidates": [],
                    "warp_cautions": [],
                    "adjacent_tiles": {},
                    "local_map": [],
                    "map_snapshot": {"available": False},
                },
                "deltas": {
                    "position_changed": False,
                    "money_delta": 0,
                    "battle_toggled": False,
                    "movement_stall_turns": 2,
                    "stuck_hint": "possibly stuck",
                },
                "movement_pattern": {"window_size": 0},
                "battle_summary": {"phase": "not_in_battle"},
            }
        )

        self.assertIn("STORY GUIDANCE:", text)
        self.assertIn("Phase: post_battle_intro_route", text)
        self.assertIn("Priority: high", text)
        self.assertIn("prioritize UP", text)

    def test_text_representation_includes_battle_guidance_and_move_labels(self):
        state = self._make_state()

        text = state.get_text_representation(
            {
                "turn": 18,
                "memory": {
                    "position": {"map_id": 12, "x": 11, "y": 32},
                    "direction": "up",
                    "badges": {},
                    "badge_count": 0,
                    "party": [
                        {
                            "species": "Charmander",
                            "level": 6,
                            "current_hp": 21,
                            "max_hp": 21,
                            "moves": [
                                {"move_id": 10, "pp": 35},
                                {"move_id": 45, "pp": 40},
                            ],
                        }
                    ],
                    "money": 3175,
                    "item_count": 0,
                    "in_battle": True,
                    "battle": {
                        "battle_type": "wild",
                        "enemy_species": "Rattata",
                        "enemy_level": 3,
                        "enemy_current_hp": 18,
                    },
                    "ui": {"text_box_active": False, "menu_active": True},
                },
                "pre_world": False,
                "pre_starter_script": False,
                "phase_hint": "battle",
                "visual": {
                    "screen_type": "battle",
                    "description": "Wild battle menu",
                    "local_analysis_enabled": False,
                    "navigation_hints": {"available": False},
                },
                "story_guidance": None,
                "exploration": {"nearby_unexplored": []},
                "map_memory": {
                    "exploration_percent": 52.5,
                    "explored_tiles": 105,
                    "total_tiles": 200,
                },
                "navigation": {
                    "current_visit_count": 1,
                    "known_exits": {},
                    "blocked_directions": [],
                    "frontier_count": 0,
                    "nearest_frontier": None,
                    "frontier_candidates": [],
                    "warp_cautions": [],
                    "adjacent_tiles": {},
                    "local_map": [],
                    "map_snapshot": {"available": False},
                },
                "deltas": {
                    "position_changed": False,
                    "money_delta": 0,
                    "battle_toggled": False,
                    "movement_stall_turns": 0,
                    "stuck_hint": "ui text or menu is active; lack of movement is expected",
                },
                "movement_pattern": {"window_size": 0},
                "battle_summary": {
                    "phase": "battle_in_progress",
                    "encounter_type": "wild",
                    "battle_turns": 6,
                    "enemy_hp_changed": False,
                    "battle_stall_turns": 1,
                    "lead_pokemon": {
                        "species": "Charmander",
                        "level": 6,
                        "current_hp": 21,
                        "max_hp": 21,
                        "hp_percent": 100.0,
                    },
                    "focus_hint": "A battle is active. Resolve the fight before returning to movement goals.",
                },
                "battle_guidance": {
                    "phase": "battle_in_progress",
                    "priority": "high",
                    "summary": (
                        "A battle menu is active. If this is the four-command menu, choose FIGHT. "
                        "If the move list is already open, pick the recommended move directly."
                    ),
                    "menu_cue": (
                        "When the standard four-command battle menu appears, prefer FIGHT over BAG, "
                        "PKMN, or RUN for this ordinary early-game encounter unless the screenshot "
                        "shows a different urgent need."
                    ),
                    "move_cue": (
                        "When the move list is open, prefer slot 1 (Scratch, PP 35); avoid "
                        "status-only options like slot 2 (Growl) while a damaging move still has PP."
                    ),
                },
            }
        )

        self.assertIn("Moves: 1:Scratch [damaging, PP:35]; 2:Growl [status, PP:40]", text)
        self.assertIn("BATTLE GUIDANCE:", text)
        self.assertIn("Menu cue: When the standard four-command battle menu appears, prefer FIGHT", text)
        self.assertIn("Move cue: When the move list is open, prefer slot 1 (Scratch, PP 35)", text)


if __name__ == "__main__":
    unittest.main()
