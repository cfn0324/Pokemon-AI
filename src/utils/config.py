"""Configuration loader and validator."""

import yaml
import os
from pathlib import Path
from typing import Dict, Any


class Config:
    """Configuration manager for the Pokemon AI Agent."""

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize configuration.

        Args:
            config_path: Path to the configuration YAML file
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Load configuration from YAML file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self._validate()
        self._setup_directories()

    def _validate(self) -> None:
        """Validate required configuration fields."""
        required_sections = ['game', 'ai', 'memory', 'actions', 'logging']

        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required configuration section: {section}")

        # Validate ROM file exists
        rom_path = self.config['game']['rom_path']
        if not os.path.exists(rom_path):
            raise FileNotFoundError(f"ROM file not found: {rom_path}")

        # Validate API key
        if not os.getenv('ANTHROPIC_API_KEY'):
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    def _setup_directories(self) -> None:
        """Create necessary directories."""
        directories = [
            self.config['game']['save_state_dir'],
            self.config['logging']['log_dir'],
            self.config['logging']['screenshot_dir'],
            self.config['performance']['cache_dir'],
            'data/maps',
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

    def get(self, path: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated path.

        Args:
            path: Dot-separated path (e.g., 'ai.model')
            default: Default value if path not found

        Returns:
            Configuration value
        """
        keys = path.split('.')
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set(self, path: str, value: Any) -> None:
        """Set configuration value by dot-separated path.

        Args:
            path: Dot-separated path (e.g., 'goals.primary_goal')
            value: Value to set
        """
        keys = path.split('.')
        config = self.config

        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        config[keys[-1]] = value

    def save(self) -> None:
        """Save current configuration to file."""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, default_flow_style=False)


# Global configuration instance
_config: Config = None


def get_config(config_path: str = "config.yaml") -> Config:
    """Get global configuration instance.

    Args:
        config_path: Path to configuration file

    Returns:
        Config instance
    """
    global _config
    if _config is None:
        _config = Config(config_path)
    return _config
