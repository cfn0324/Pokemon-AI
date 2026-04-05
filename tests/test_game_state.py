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


if __name__ == "__main__":
    unittest.main()
