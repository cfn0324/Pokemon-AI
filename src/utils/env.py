"""Environment helpers for AI configuration."""

from __future__ import annotations

import os


LEGACY_ENV_ALIASES = {
    "AI_API_KEY": "ANTHROPIC_API_KEY",
    "AI_BASE_URL": "ANTHROPIC_BASE_URL",
    "AI_MODEL": "ANTHROPIC_MODEL",
}


def apply_env_aliases() -> None:
    """Populate current AI env vars from legacy names when needed."""
    for current_name, legacy_name in LEGACY_ENV_ALIASES.items():
        if not os.getenv(current_name):
            legacy_value = os.getenv(legacy_name)
            if legacy_value:
                os.environ[current_name] = legacy_value
