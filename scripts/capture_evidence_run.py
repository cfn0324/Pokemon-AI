"""Run the main agent from a checkpoint and capture dense screenshot evidence."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import PokemonAIAgent
from src.runtime.checkpoints import load_checkpoint_metadata
from src.utils.config import get_config


def _resolve_checkpoint_name(raw_name: str) -> str:
    checkpoint_name = str(raw_name or "").strip()
    if not checkpoint_name:
        raise ValueError("Checkpoint name is required.")
    return checkpoint_name


def _load_checkpoint_turn(checkpoint_name: str, checkpoint_root: Path) -> int:
    checkpoint_dir = checkpoint_root / checkpoint_name
    if not checkpoint_dir.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_dir}")
    metadata = load_checkpoint_metadata(checkpoint_dir)
    return int(metadata.get("turn", 0) or 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the main agent from a checkpoint and save screenshot evidence.",
    )
    parser.add_argument(
        "--checkpoint",
        required=True,
        help="Checkpoint directory name under data/checkpoints.",
    )
    parser.add_argument(
        "--turns",
        type=int,
        default=120,
        help="How many turns to execute after restoring the checkpoint.",
    )
    parser.add_argument(
        "--screenshot-dir",
        required=True,
        help="Directory that receives the generated screenshots.",
    )
    parser.add_argument(
        "--screenshot-interval",
        type=int,
        default=1,
        help="Save one screenshot every N turns.",
    )
    parser.add_argument(
        "--disable-visualizer",
        action="store_true",
        help="Disable the live web visualizer during the evidence run.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the evidence capture headlessly.",
    )
    parser.add_argument(
        "--pure-llm",
        action="store_true",
        help="Force pure-LLM control for the evidence run.",
    )
    parser.add_argument(
        "--disable-runtime-fallbacks",
        action="store_true",
        help="Disable runtime fallback/tool takeover behavior during capture.",
    )
    parser.add_argument(
        "--reset-context",
        action="store_true",
        help="Clear saved context after restoring the checkpoint.",
    )
    return parser


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    checkpoint_name = _resolve_checkpoint_name(args.checkpoint)
    screenshot_dir = Path(args.screenshot_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    config = get_config()
    checkpoint_root = Path(config.get("game.save_state_dir"))
    start_turn = _load_checkpoint_turn(checkpoint_name, checkpoint_root)
    end_turn = start_turn + max(1, int(args.turns))

    config.set("game.resume_checkpoint", None)
    config.set("game.auto_resume_latest_checkpoint", False)
    config.set("game.prompt_for_checkpoint_on_start", False)
    config.set("testing.write_checkpoints", False)
    config.set("game.speed", 0)
    config.set("logging.save_screenshots", True)
    config.set("logging.annotate_screenshots", False)
    config.set("logging.screenshot_dir", str(screenshot_dir))
    config.set("actions.screenshot_interval", max(1, int(args.screenshot_interval)))
    config.set("testing.max_turns", end_turn)
    config.set("performance.async_decisions", False)
    if args.headless:
        config.set("game.headless", True)
    if args.disable_visualizer:
        config.set("visualization.enabled", False)
    if args.disable_runtime_fallbacks:
        config.set("decision.disable_runtime_fallbacks", True)
    if args.pure_llm:
        config.set("decision.pure_llm_mode", True)
        config.set("decision.llm_primary_mode", False)
        config.set("decision.ai_full_control_mode", False)
        config.set("decision.disable_runtime_fallbacks", True)
        config.set("ai.guidance_interval_turns", 0)
        config.set("ai.agents.main.temperature", 0.0)
        config.set("decision.retry_same_turn_on_ai_error", True)
        config.set("decision.same_turn_retry_max_attempts", 60)
        config.set("decision.same_turn_retry_timeout_seconds", 60)
        config.set("decision.same_turn_retry_min_delay_seconds", 0.25)
        config.set("ai.request_timeout_seconds", 30)
        config.set("ai.request_retries", 2)
        config.set("ai.request_retry_backoff_seconds", 0.5)
        config.set("ai.api_error_cooldown_seconds", 1)
        config.set("ai.api_error_cooldown_max_seconds", 2)
        config.set("ai.persistent_api_error_cooldown_seconds", 2)
        config.set("ai.unreachable_api_error_cooldown_seconds", 2)

    print(
        "[capture_evidence_run] "
        f"checkpoint={checkpoint_name} start_turn={start_turn} "
        f"end_turn={end_turn} screenshot_dir={screenshot_dir} "
        f"screenshot_interval={config.get('actions.screenshot_interval')} "
        f"pure_llm={bool(config.get('decision.pure_llm_mode', False))} "
        f"disable_runtime_fallbacks={bool(config.get('decision.disable_runtime_fallbacks', False))} "
        f"headless={bool(config.get('game.headless', False))} "
        f"reset_context={bool(args.reset_context)}"
    )

    agent = PokemonAIAgent()
    agent._load_checkpoint(checkpoint_name, pause_after_load=False)
    if args.reset_context:
        agent.main_agent.context.clear()
    agent.max_turns = end_turn
    agent.run()

    images = sorted(screenshot_dir.glob("turn_*.png"))
    print(
        "[capture_evidence_run] "
        f"finished turn_count={agent.turn_count} saved_images={len(images)} "
        f"fatal_error={getattr(agent, '_last_fatal_error', None)}"
    )


if __name__ == "__main__":
    main()
