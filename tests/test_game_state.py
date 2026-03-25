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


if __name__ == "__main__":
    unittest.main()
