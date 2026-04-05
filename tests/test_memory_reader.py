import unittest

from src.emulator.memory_reader import MemoryReader


class _FakeEmulator:
    def __init__(self, memory=None):
        self.memory = dict(memory or {})

    def read_memory(self, address):
        return int(self.memory.get(address, 0))

    def read_memory_range(self, address, length):
        return bytes(self.read_memory(address + i) for i in range(length))


class MemoryReaderTests(unittest.TestCase):
    def test_party_reads_big_endian_hp_and_alias_fields(self):
        emulator = _FakeEmulator()
        reader = MemoryReader(emulator)

        count_addr = int(reader.memory_map["party"]["count"]["address"], 16)
        base_addr = int(reader.memory_map["party"]["pokemon"]["base_address"], 16)
        fields = reader.memory_map["party"]["pokemon"]["fields"]
        species_id = 176

        emulator.memory[count_addr] = 1
        emulator.memory[base_addr + fields["species"]["offset"]] = species_id
        emulator.memory[base_addr + fields["current_hp"]["offset"]] = 0x00
        emulator.memory[base_addr + fields["current_hp"]["offset"] + 1] = 0x16
        emulator.memory[base_addr + fields["max_hp"]["offset"]] = 0x00
        emulator.memory[base_addr + fields["max_hp"]["offset"] + 1] = 0x18
        emulator.memory[base_addr + fields["level"]["offset"]] = 6
        emulator.memory[base_addr + fields["move1"]["offset"]] = 10
        emulator.memory[base_addr + fields["move1_pp"]["offset"]] = 35

        party = reader.read_party()

        self.assertEqual(len(party), 1)
        starter = party[0]
        self.assertEqual(starter["species_id"], species_id)
        self.assertEqual(starter["species"], reader.POKEMON_NAMES[species_id])
        self.assertEqual(starter["name"], starter["species"])
        self.assertEqual(starter["display_name"], starter["species"])
        self.assertEqual(starter["current_hp"], 22)
        self.assertEqual(starter["hp"], 22)
        self.assertEqual(starter["max_hp"], 24)
        self.assertEqual(starter["level"], 6)
        self.assertEqual(starter["moves"], [{"move_id": 10, "pp": 35}])

    def test_reads_story_event_flags_from_w_event_flags(self):
        emulator = _FakeEmulator()
        reader = MemoryReader(emulator)

        events_meta = reader.memory_map["events"]["flags"]
        base_addr = int(events_meta["address"], 16)

        emulator.memory[base_addr + (37 // 8)] = 1 << (37 % 8)
        emulator.memory[base_addr + (56 // 8)] = 1 << (56 % 8)

        events = reader.read_story_events()
        summary = reader.get_game_state_summary()

        self.assertEqual(
            events,
            {
                "got_pokedex": True,
                "oak_got_parcel": True,
                "got_oaks_parcel": False,
            },
        )
        self.assertEqual(summary["events"], events)

    def test_is_in_battle_distinguishes_none_wild_trainer_and_lost(self):
        emulator = _FakeEmulator()
        reader = MemoryReader(emulator)
        state_addr = int(reader.memory_map["battle"]["in_battle"]["address"], 16)

        emulator.memory[state_addr] = 0
        self.assertFalse(reader.is_in_battle())

        emulator.memory[state_addr] = 1
        self.assertTrue(reader.is_in_battle())

        emulator.memory[state_addr] = 2
        self.assertTrue(reader.is_in_battle())

        emulator.memory[state_addr] = 0xFF
        self.assertFalse(reader.is_in_battle())

    def test_battle_info_uses_encounter_state_for_wild_and_trainer(self):
        emulator = _FakeEmulator()
        reader = MemoryReader(emulator)

        state_addr = int(reader.memory_map["battle"]["in_battle"]["address"], 16)
        mode_addr = int(reader.memory_map["battle"]["mode"]["address"], 16)
        enemy_meta = reader.memory_map["battle"]["enemy_mon"]
        species_addr = int(enemy_meta["species"]["address"], 16)
        hp_addr = int(enemy_meta["current_hp"]["address"], 16)
        level_addr = int(enemy_meta["level"]["address"], 16)

        emulator.memory[species_addr] = 36
        emulator.memory[level_addr] = 3
        emulator.memory[hp_addr] = 0x00
        emulator.memory[hp_addr + 1] = 0x12
        emulator.memory[mode_addr] = 0

        emulator.memory[state_addr] = 1
        wild_info = reader.read_battle_info()
        self.assertEqual(wild_info["battle_type"], "wild")
        self.assertEqual(wild_info["battle_mode"], "normal")

        emulator.memory[state_addr] = 2
        trainer_info = reader.read_battle_info()
        self.assertEqual(trainer_info["battle_type"], "trainer")
        self.assertEqual(trainer_info["enemy_species"], "Pidgey")


if __name__ == "__main__":
    unittest.main()
