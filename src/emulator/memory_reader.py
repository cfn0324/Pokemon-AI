"""Memory reader for Pokemon Red game state."""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path

from .game_boy import GameBoyEmulator
from ..utils.logger import get_logger


class MemoryReader:
    """Reads and interprets Pokemon Red memory."""

    # Pokemon species names (first 151)
    POKEMON_NAMES = [
        "None", "Rhydon", "Kangaskhan", "Nidoran♂", "Clefairy", "Spearow",
        "Voltorb", "Nidoking", "Slowbro", "Ivysaur", "Exeggutor", "Lickitung",
        "Exeggcute", "Grimer", "Gengar", "Nidoran♀", "Nidoqueen", "Cubone",
        "Rhyhorn", "Lapras", "Arcanine", "Mew", "Gyarados", "Shellder",
        "Tentacool", "Gastly", "Scyther", "Staryu", "Blastoise", "Pinsir",
        "Tangela", "Missingno", "Missingno", "Growlithe", "Onix", "Fearow",
        "Pidgey", "Slowpoke", "Kadabra", "Graveler", "Chansey", "Machoke",
        "Mr. Mime", "Hitmonlee", "Hitmonchan", "Arbok", "Parasect", "Psyduck",
        "Drowzee", "Golem", "Missingno", "Magmar", "Missingno", "Electabuzz",
        "Magneton", "Koffing", "Missingno", "Mankey", "Seel", "Diglett",
        "Tauros", "Missingno", "Missingno", "Missingno", "Farfetch'd", "Venonat",
        "Dragonite", "Missingno", "Missingno", "Missingno", "Doduo", "Poliwag",
        "Jynx", "Moltres", "Articuno", "Zapdos", "Ditto", "Meowth",
        "Krabby", "Missingno", "Missingno", "Missingno", "Vulpix", "Ninetales",
        "Pikachu", "Raichu", "Missingno", "Missingno", "Dratini", "Dragonair",
        "Kabuto", "Kabutops", "Horsea", "Seadra", "Missingno", "Missingno",
        "Sandshrew", "Sandslash", "Omanyte", "Omastar", "Jigglypuff", "Wigglytuff",
        "Eevee", "Flareon", "Jolteon", "Vaporeon", "Machop", "Zubat",
        "Ekans", "Parasect", "Poliwhirl", "Poliwrath", "Weedle", "Kakuna",
        "Beedrill", "Missingno", "Dodrio", "Primeape", "Dugtrio", "Venomoth",
        "Dewgong", "Missingno", "Missingno", "Caterpie", "Metapod", "Butterfree",
        "Machamp", "Missingno", "Golduck", "Hypno", "Golbat", "Mewtwo",
        "Snorlax", "Magikarp", "Missingno", "Missingno", "Muk", "Missingno",
        "Kingler", "Cloyster", "Missingno", "Electrode", "Clefable", "Weezing",
        "Persian", "Marowak", "Missingno", "Haunter", "Abra", "Alakazam",
        "Pidgeotto", "Pidgeot", "Starmie", "Bulbasaur", "Venusaur", "Tentacruel",
        "Missingno", "Goldeen", "Seaking", "Missingno", "Missingno", "Missingno",
        "Missingno", "Ponyta", "Rapidash", "Rattata", "Raticate", "Nidorino",
        "Nidorina", "Geodude", "Porygon", "Aerodactyl", "Missingno", "Magnemite",
        "Missingno", "Missingno", "Charmander", "Squirtle", "Charmeleon", "Wartortle",
        "Charizard", "Missingno", "Missingno", "Missingno", "Missingno", "Oddish",
        "Gloom", "Vileplume", "Bellsprout", "Weepinbell", "Victreebel"
    ]

    def __init__(self, emulator: GameBoyEmulator, memory_map_path: str = "data/memory_addresses.json"):
        """Initialize memory reader.

        Args:
            emulator: GameBoy emulator instance
            memory_map_path: Path to memory address mapping JSON
        """
        self.emulator = emulator
        self.logger = get_logger('MemoryReader')

        # Load memory map
        with open(memory_map_path, 'r') as f:
            self.memory_map = json.load(f)

        self.logger.info("Memory reader initialized")

    def read_player_position(self) -> Dict[str, int]:
        """Read player position.

        Returns:
            Dict with x, y, map_id
        """
        x = self.emulator.read_memory(int(self.memory_map['player']['position']['x']['address'], 16))
        y = self.emulator.read_memory(int(self.memory_map['player']['position']['y']['address'], 16))
        map_id = self.emulator.read_memory(int(self.memory_map['player']['position']['map_id']['address'], 16))

        return {'x': x, 'y': y, 'map_id': map_id}

    def read_badges(self) -> Dict[str, bool]:
        """Read badge status.

        Returns:
            Dict mapping badge names to obtained status
        """
        badge_byte = self.emulator.read_memory(int(self.memory_map['badges']['address'], 16))
        badges = {}

        for bit, name in self.memory_map['badges']['bits'].items():
            badges[name] = bool(badge_byte & (1 << int(bit)))

        return badges

    def count_badges(self) -> int:
        """Count number of badges obtained.

        Returns:
            Number of badges
        """
        return sum(self.read_badges().values())

    def read_party(self) -> List[Dict[str, Any]]:
        """Read Pokemon party.

        Returns:
            List of Pokemon data
        """
        party_count = self.emulator.read_memory(int(self.memory_map['party']['count']['address'], 16))

        if party_count == 0 or party_count > 6:
            return []

        party = []
        base_addr = int(self.memory_map['party']['pokemon']['base_address'], 16)
        size = self.memory_map['party']['pokemon']['size']

        for i in range(party_count):
            pokemon_addr = base_addr + (i * size)
            pokemon_data = self._read_pokemon(pokemon_addr)
            party.append(pokemon_data)

        return party

    def _read_pokemon(self, base_address: int) -> Dict[str, Any]:
        """Read individual Pokemon data.

        Args:
            base_address: Base address of Pokemon data

        Returns:
            Pokemon data dict
        """
        fields = self.memory_map['party']['pokemon']['fields']

        species_id = self.emulator.read_memory(base_address + fields['species']['offset'])
        species_name = self.POKEMON_NAMES[species_id] if species_id < len(self.POKEMON_NAMES) else "Unknown"

        # Read HP (16-bit)
        current_hp = self._read_uint16(base_address + fields['current_hp']['offset'])
        max_hp = self._read_uint16(base_address + fields['max_hp']['offset'])

        # Read level
        level = self.emulator.read_memory(base_address + fields['level']['offset'])

        # Read moves and PP
        moves = []
        for i in range(1, 5):
            move_id = self.emulator.read_memory(base_address + fields[f'move{i}']['offset'])
            pp = self.emulator.read_memory(base_address + fields[f'move{i}_pp']['offset'])
            if move_id > 0:
                moves.append({'move_id': move_id, 'pp': pp})

        # Read stats
        attack = self._read_uint16(base_address + fields['attack']['offset'])
        defense = self._read_uint16(base_address + fields['defense']['offset'])
        speed = self._read_uint16(base_address + fields['speed']['offset'])
        special = self._read_uint16(base_address + fields['special']['offset'])

        return {
            'species_id': species_id,
            'species': species_name,
            'level': level,
            'current_hp': current_hp,
            'max_hp': max_hp,
            'moves': moves,
            'stats': {
                'attack': attack,
                'defense': defense,
                'speed': speed,
                'special': special
            }
        }

    def _read_uint16(self, address: int) -> int:
        """Read 16-bit unsigned integer (little-endian).

        Args:
            address: Memory address

        Returns:
            16-bit value
        """
        low = self.emulator.read_memory(address)
        high = self.emulator.read_memory(address + 1)
        return (high << 8) | low

    def read_money(self) -> int:
        """Read player money (BCD encoded).

        Returns:
            Money amount
        """
        address = int(self.memory_map['player']['money']['address'], 16)
        bcd_bytes = self.emulator.read_memory_range(address, 3)

        # Convert BCD to decimal
        money = 0
        for byte in bcd_bytes:
            high = (byte >> 4) & 0xF
            low = byte & 0xF
            money = money * 100 + high * 10 + low

        return money

    def is_in_battle(self) -> bool:
        """Check if currently in battle.

        Returns:
            True if in battle
        """
        battle_type = self.emulator.read_memory(int(self.memory_map['battle']['in_battle']['address'], 16))
        return battle_type != 0

    def get_game_state_summary(self) -> Dict[str, Any]:
        """Get comprehensive game state summary.

        Returns:
            Dict with all relevant game state
        """
        return {
            'position': self.read_player_position(),
            'badges': self.read_badges(),
            'badge_count': self.count_badges(),
            'party': self.read_party(),
            'money': self.read_money(),
            'in_battle': self.is_in_battle(),
        }
