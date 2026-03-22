"""Game Boy emulator wrapper using PyBoy."""

import threading
from typing import Optional, Tuple
import numpy as np
from PIL import Image
from pyboy import PyBoy
from pyboy.utils import WindowEvent

from ..utils.logger import get_logger
from ..utils.config import get_config


class GameBoyEmulator:
    """Wrapper for PyBoy emulator with Pokemon Red specific functionality."""

    # Button mappings
    BUTTONS = {
        'a': WindowEvent.PRESS_BUTTON_A,
        'b': WindowEvent.PRESS_BUTTON_B,
        'start': WindowEvent.PRESS_BUTTON_START,
        'select': WindowEvent.PRESS_BUTTON_SELECT,
        'up': WindowEvent.PRESS_ARROW_UP,
        'down': WindowEvent.PRESS_ARROW_DOWN,
        'left': WindowEvent.PRESS_ARROW_LEFT,
        'right': WindowEvent.PRESS_ARROW_RIGHT,
    }

    RELEASE_BUTTONS = {
        'a': WindowEvent.RELEASE_BUTTON_A,
        'b': WindowEvent.RELEASE_BUTTON_B,
        'start': WindowEvent.RELEASE_BUTTON_START,
        'select': WindowEvent.RELEASE_BUTTON_SELECT,
        'up': WindowEvent.RELEASE_ARROW_UP,
        'down': WindowEvent.RELEASE_ARROW_DOWN,
        'left': WindowEvent.RELEASE_ARROW_LEFT,
        'right': WindowEvent.RELEASE_ARROW_RIGHT,
    }

    def __init__(self, rom_path: str, headless: bool = False, speed: int = 0):
        """Initialize the emulator.

        Args:
            rom_path: Path to Pokemon Red ROM file
            headless: Run without displaying window
            speed: Emulation speed (0=unlimited, 1=normal, 2+=slower)
        """
        self.config = get_config()
        self.logger = get_logger('Emulator')

        self.logger.info(f"Initializing emulator with ROM: {rom_path}")

        # Initialize PyBoy
        self.pyboy = PyBoy(
            rom_path,
            window="null" if headless else "SDL2",
            debug=False,
        )

        self.speed = speed
        self.frame_count = 0
        self._lock = threading.RLock()

        self.logger.info("Emulator initialized successfully")

    def tick(self, ticks: int = 1) -> None:
        """Advance emulator by N ticks.

        Args:
            ticks: Number of ticks to advance
        """
        for _ in range(ticks):
            with self._lock:
                self.pyboy.tick()
                self.frame_count += 1

    def tick_with_events(self, ticks: int = 1) -> None:
        """Advance emulator by N ticks while processing window events.

        This prevents the window from becoming unresponsive.

        Args:
            ticks: Number of ticks to advance
        """
        for _ in range(ticks):
            with self._lock:
                # PyBoy's tick() already handles events internally
                # Just call tick() which processes both game logic and window events
                self.pyboy.tick()
                self.frame_count += 1

    def press_button(
        self,
        button: str,
        duration: Optional[int] = None,
        release_delay: Optional[int] = None,
    ) -> None:
        """Press a button for specified duration.

        Args:
            button: Button name (a, b, start, select, up, down, left, right)
            duration: Number of frames to hold button
            release_delay: Frames to wait after releasing the button
        """
        if button not in self.BUTTONS:
            self.logger.warning(f"Invalid button: {button}")
            return

        if duration is None:
            if button in {"up", "down", "left", "right"}:
                duration = int(self.config.get("actions.direction_press_frames", 2) or 2)
            else:
                duration = int(self.config.get("actions.button_press_frames", 3) or 3)

        if release_delay is None:
            if button in {"up", "down", "left", "right"}:
                release_delay = int(self.config.get("actions.direction_release_frames", 4) or 4)
            else:
                release_delay = int(self.config.get("actions.button_release_frames", 6) or 6)

        self.logger.debug(f"Pressing button: {button} for {duration} frames")

        with self._lock:
            self.pyboy.send_input(self.BUTTONS[button])
        self.tick(max(1, duration))

        with self._lock:
            self.pyboy.send_input(self.RELEASE_BUTTONS[button])
        self.tick(max(1, release_delay))

    def get_screen_image(self) -> Image.Image:
        """Get current screen as PIL Image.

        Returns:
            PIL Image of current screen
        """
        # Get screen buffer from PyBoy
        with self._lock:
            screen_array = self.pyboy.screen.ndarray.copy()

        # Convert to PIL Image
        image = Image.fromarray(screen_array)

        return image

    def get_screen_array(self) -> np.ndarray:
        """Get current screen as numpy array.

        Returns:
            Numpy array of screen (160x144x3)
        """
        with self._lock:
            return self.pyboy.screen.ndarray.copy()

    def read_memory(self, address: int) -> int:
        """Read a byte from memory.

        Args:
            address: Memory address to read

        Returns:
            Byte value at address
        """
        with self._lock:
            return self.pyboy.memory[address]

    def read_memory_range(self, address: int, length: int) -> bytes:
        """Read multiple bytes from memory.

        Args:
            address: Starting memory address
            length: Number of bytes to read

        Returns:
            Bytes from memory
        """
        with self._lock:
            return bytes([self.pyboy.memory[address + i] for i in range(length)])

    def write_memory(self, address: int, value: int) -> None:
        """Write a byte to memory.

        Args:
            address: Memory address to write
            value: Byte value to write
        """
        with self._lock:
            self.pyboy.memory[address] = value

    def save_state(self, filename: str) -> None:
        """Save emulator state.

        Args:
            filename: Path to save state file
        """
        self.logger.info(f"Saving state to: {filename}")
        with self._lock:
            with open(filename, "wb") as f:
                self.pyboy.save_state(f)

    def load_state(self, filename: str) -> None:
        """Load emulator state.

        Args:
            filename: Path to state file
        """
        self.logger.info(f"Loading state from: {filename}")
        with self._lock:
            with open(filename, "rb") as f:
                self.pyboy.load_state(f)

    def stop(self) -> None:
        """Stop the emulator."""
        self.logger.info("Stopping emulator")
        with self._lock:
            self.pyboy.stop()

    def get_sprite_positions(self) -> list:
        """Get all sprite positions on screen.

        Returns:
            List of sprite data
        """
        # This would extract sprite data from OAM
        # For now, return empty list
        return []

    def is_running(self) -> bool:
        """Check if emulator is still running.

        Returns:
            True if running
        """
        # PyBoy doesn't expose a shutdown status, just return True
        # The emulator will raise an exception if it's actually shut down
        return True
