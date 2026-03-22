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


if __name__ == "__main__":
    unittest.main()
