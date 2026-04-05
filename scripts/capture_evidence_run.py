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

    config.set("game.resume_checkpoint", checkpoint_name)
    config.set("game.auto_resume_latest_checkpoint", False)
    config.set("game.prompt_for_checkpoint_on_start", False)
    config.set("logging.save_screenshots", True)
    config.set("logging.screenshot_dir", str(screenshot_dir))
    config.set("actions.screenshot_interval", max(1, int(args.screenshot_interval)))
    config.set("testing.max_turns", end_turn)
    if args.disable_visualizer:
        config.set("visualization.enabled", False)

    print(
        "[capture_evidence_run] "
        f"checkpoint={checkpoint_name} start_turn={start_turn} "
        f"end_turn={end_turn} screenshot_dir={screenshot_dir} "
        f"screenshot_interval={config.get('actions.screenshot_interval')}"
    )

    agent = PokemonAIAgent()
    agent.run()

    images = sorted(screenshot_dir.glob("turn_*.png"))
    print(
        "[capture_evidence_run] "
        f"finished turn_count={agent.turn_count} saved_images={len(images)} "
        f"fatal_error={getattr(agent, '_last_fatal_error', None)}"
    )


if __name__ == "__main__":
    main()
