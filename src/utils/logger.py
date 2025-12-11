"""Logging utilities with color support."""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import colorlog


class PokemonLogger:
    """Custom logger for Pokemon AI Agent with color support."""

    def __init__(self, name: str, log_dir: str = "logs", level: str = "INFO"):
        """Initialize logger.

        Args:
            name: Logger name
            log_dir: Directory for log files
            level: Logging level
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))

        # Prevent duplicate handlers
        if self.logger.handlers:
            return

        # Console handler with colors
        console_handler = colorlog.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))

        console_format = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s%(reset)s - %(message)s',
            datefmt='%H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(console_format)

        # File handler (no colors) with UTF-8 encoding
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_handler = logging.FileHandler(
            self.log_dir / f"{name}_{timestamp}.log",
            encoding='utf-8',
            errors='replace'  # Replace problematic characters
        )
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file

        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)

        # Add handlers
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log debug message."""
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        """Log info message."""
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log warning message."""
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        """Log error message."""
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log critical message."""
        self.logger.critical(msg, *args, **kwargs)

    def action(self, action: str, details: str = "") -> None:
        """Log an action taken by the agent."""
        msg = f"ACTION: {action}"
        if details:
            msg += f" | {details}"
        self.info(msg)

    def state(self, state_type: str, data: dict) -> None:
        """Log game state information."""
        self.debug(f"STATE[{state_type}]: {data}")

    def decision(self, decision: str, reasoning: str = "") -> None:
        """Log AI decision with reasoning."""
        msg = f"DECISION: {decision}"
        if reasoning:
            msg += f" | Reasoning: {reasoning}"
        self.info(msg)

    def milestone(self, milestone: str) -> None:
        """Log important milestones."""
        self.info(f"{'='*50}")
        self.info(f"MILESTONE: {milestone}")
        self.info(f"{'='*50}")


def get_logger(name: str, log_dir: str = "logs", level: str = "INFO") -> PokemonLogger:
    """Get a logger instance.

    Args:
        name: Logger name
        log_dir: Directory for log files
        level: Logging level

    Returns:
        PokemonLogger instance
    """
    return PokemonLogger(name, log_dir, level)
