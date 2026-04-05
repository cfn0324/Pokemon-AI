"""Replay a validated story trace and capture thesis-ready location screenshots."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from PIL import Image
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.emulator.game_boy import GameBoyEmulator
from src.emulator.memory_reader import MemoryReader
from src.tools.action_executor import ActionExecutor
from src.utils.config import get_config
from src.utils.env import apply_env_aliases


TRACE_PATH = PROJECT_ROOT / "tmp" / "codex_smoke_2600_20260405_after_forced_plan_fix.json"
CHECKPOINT_PATH = PROJECT_ROOT / "data" / "checkpoints" / "checkpoint_195913" / "emulator.state"
OUTPUT_ROOT = PROJECT_ROOT / "docs" / "img" / "2026-04-05"
MAIN_FIGURE_DIR = OUTPUT_ROOT / "main_figures"
RAW_DIR = OUTPUT_ROOT / "curated_gameplay" / "raw"
MANIFEST_PATH = OUTPUT_ROOT / "curated_gameplay" / "manifest.json"


@dataclass(frozen=True)
class CaptureTarget:
    key: str
    figure_name: str
    turn: int
    map_id: int
    x: int
    y: int
    title: str
    caption: str


CAPTURE_TARGETS: List[CaptureTarget] = [
    CaptureTarget(
        key="oaks_lab_departure",
        figure_name="fig03_oaks_lab_departure.png",
        turn=195914,
        map_id=40,
        x=4,
        y=8,
        title="Oak's Lab departure scene",
        caption="Oak's Lab: the run starts by leaving the first mandatory indoor story location after the rival battle.",
    ),
    CaptureTarget(
        key="pallet_town_departure",
        figure_name="fig04_pallet_town_departure.png",
        turn=195928,
        map_id=0,
        x=16,
        y=7,
        title="Pallet Town northbound departure",
        caption="Pallet Town: the agent follows the town's east-side lane and lines up with the north exit toward Route 1.",
    ),
    CaptureTarget(
        key="route1_exploration",
        figure_name="fig05_route1_exploration.png",
        turn=196009,
        map_id=12,
        x=9,
        y=28,
        title="Route 1 exploration corridor",
        caption="Route 1: outdoor navigation continues through the grass-and-hedge corridor, showing meaningful route traversal rather than indoor looping.",
    ),
    CaptureTarget(
        key="viridian_city_arrival",
        figure_name="fig06_viridian_city_arrival.png",
        turn=196131,
        map_id=1,
        x=19,
        y=25,
        title="Viridian City arrival",
        caption="Viridian City: the run reaches the first city hub and proceeds along the main road toward the Pokemart objective.",
    ),
    CaptureTarget(
        key="viridian_mart_parcel",
        figure_name="fig07_viridian_mart_parcel.png",
        turn=196168,
        map_id=42,
        x=2,
        y=5,
        title="Viridian Mart parcel interaction",
        caption="Viridian Mart: the mandatory parcel dialogue is active, which makes the screenshot useful for explaining task-driven NPC interaction.",
    ),
    CaptureTarget(
        key="route2_northbound",
        figure_name="fig08_route2_northbound.png",
        turn=196752,
        map_id=13,
        x=7,
        y=61,
        title="Route 2 northbound progression",
        caption="Route 2: after returning the parcel and receiving the Pokedex, the agent pushes into the next outdoor route toward Viridian Forest.",
    ),
    CaptureTarget(
        key="viridian_forest_gate",
        figure_name="fig09_viridian_forest_gate.png",
        turn=196924,
        map_id=50,
        x=4,
        y=3,
        title="Viridian Forest south gate transition",
        caption="Viridian Forest south gate: the run passes through the building transition that connects Route 2 to the forest entrance.",
    ),
    CaptureTarget(
        key="viridian_forest_entry",
        figure_name="fig10_viridian_forest_entry.png",
        turn=196956,
        map_id=51,
        x=12,
        y=43,
        title="Viridian Forest interior entry",
        caption="Viridian Forest: the run has entered the forest interior and started navigating a denser, more complex map layout.",
    ),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay a validated trace and capture curated location screenshots.",
    )
    parser.add_argument(
        "--trace",
        default=str(TRACE_PATH),
        help="Trace JSON to replay.",
    )
    parser.add_argument(
        "--checkpoint",
        default=str(CHECKPOINT_PATH),
        help="Checkpoint emulator.state file to restore before replay.",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=6,
        help="Nearest-neighbor upscale factor for thesis figures.",
    )
    parser.add_argument(
        "--direction-retries",
        type=int,
        default=3,
        help="How many times to retry a directional input when a trace step under-moves.",
    )
    return parser.parse_args()


def load_trace(trace_path: Path) -> Dict[str, object]:
    return json.loads(trace_path.read_text(encoding="utf-8"))


def upscale_image(image: Image.Image, scale: int) -> Image.Image:
    scale = max(1, int(scale))
    if scale == 1:
        return image.copy()
    return image.resize(
        (image.width * scale, image.height * scale),
        resample=Image.Resampling.NEAREST,
    )


def normalize_position(memory_reader: MemoryReader) -> Dict[str, int]:
    position = memory_reader.read_player_position()
    return {
        "map_id": int(position.get("map_id", -1)),
        "x": int(position.get("x", -1)),
        "y": int(position.get("y", -1)),
    }


def row_position(row: Dict[str, object]) -> Dict[str, int]:
    position = row.get("position") or {}
    return {
        "map_id": int(position.get("map_id", -1)),
        "x": int(position.get("x", -1)),
        "y": int(position.get("y", -1)),
    }


def settle_override_for_row(
    config,
    row: Dict[str, object],
    action: str,
) -> Optional[int]:
    normalized = action.strip().lower()
    if normalized not in {"a", "b"}:
        return None

    source = str(row.get("decision_source") or "").strip().lower()
    if source == "early_battle":
        return max(
            0,
            int(config.get("actions.early_battle_button_settle_frames", 30) or 30),
        )

    screen_type = str(row.get("screen_type") or "").strip().lower()
    if screen_type == "battle":
        return max(
            0,
            int(config.get("actions.ai_battle_text_button_settle_frames", 24) or 24),
        )
    return None


def precise_for_row(row: Dict[str, object], action: str) -> bool:
    normalized = action.strip().lower()
    if normalized not in {"up", "down", "left", "right"}:
        return False
    source = str(row.get("decision_source") or "").strip().lower()
    return source not in {"ai", "cached_ai_plan"}


def ensure_capture_dirs() -> None:
    MAIN_FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)


def settle_to_expected_position(
    emulator: GameBoyEmulator,
    memory_reader: MemoryReader,
    expected: Dict[str, int],
    *,
    max_frames: int,
) -> bool:
    if normalize_position(memory_reader) == expected:
        return True

    for _ in range(max(1, int(max_frames))):
        emulator.tick(1)
        if normalize_position(memory_reader) == expected:
            return True
    return False


def capture_current_screen(
    emulator: GameBoyEmulator,
    target: CaptureTarget,
    scale: int,
) -> Dict[str, object]:
    raw_path = RAW_DIR / f"turn_{target.turn}_{target.key}.png"
    figure_path = MAIN_FIGURE_DIR / target.figure_name

    image = emulator.get_screen_image()
    image.save(raw_path)
    upscale_image(image, scale).save(figure_path)

    return {
        "key": target.key,
        "turn": target.turn,
        "map_id": target.map_id,
        "x": target.x,
        "y": target.y,
        "title": target.title,
        "caption": target.caption,
        "raw_path": str(raw_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "figure_path": str(figure_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
    }


def force_advance_to_next_row(
    emulator: GameBoyEmulator,
    memory_reader: MemoryReader,
    executor: ActionExecutor,
    config,
    row: Dict[str, object],
    next_expected: Dict[str, int],
    direction_retries: int,
) -> None:
    action = str(row.get("action") or "").strip().lower()
    settle_override = settle_override_for_row(config, row, action)
    precise = precise_for_row(row, action)

    if settle_to_expected_position(emulator, memory_reader, next_expected, max_frames=24):
        return

    if action in {"up", "down", "left", "right"}:
        for _ in range(max(0, int(direction_retries))):
            executor.execute(
                action,
                precise=precise,
                settle_frames_override=settle_override,
            )
            if settle_to_expected_position(emulator, memory_reader, next_expected, max_frames=24):
                return

    if settle_to_expected_position(emulator, memory_reader, next_expected, max_frames=180):
        return

    raise RuntimeError(
        f"Replay failed to reach next trace position {next_expected}; got {normalize_position(memory_reader)} "
        f"after action {action!r} at turn {row.get('turn')}"
    )


def replay_and_capture(
    trace: Dict[str, object],
    checkpoint_path: Path,
    scale: int,
    direction_retries: int,
) -> List[Dict[str, object]]:
    config = get_config()
    config.set("game.headless", True)
    config.set("game.speed", 0)

    emulator = GameBoyEmulator(
        str(PROJECT_ROOT / str(config.get("game.rom_path"))),
        headless=True,
        speed=0,
    )
    memory_reader = MemoryReader(emulator)
    executor = ActionExecutor(emulator, memory_reader)

    try:
        emulator.load_state(str(checkpoint_path))
        executor.reset_stuck_detection()
        timeline: List[Dict[str, object]] = list(trace.get("timeline") or [])

        targets_by_turn = {target.turn: target for target in CAPTURE_TARGETS}
        captures: List[Dict[str, object]] = []

        for index, row in enumerate(timeline):
            turn = int(row.get("turn", -1))
            expected_before = row_position(row)
            if not settle_to_expected_position(
                emulator,
                memory_reader,
                expected_before,
                max_frames=180,
            ):
                raise RuntimeError(
                    f"Replay failed to settle onto trace position {expected_before} before turn {turn}; "
                    f"got {normalize_position(memory_reader)}"
                )

            if turn in targets_by_turn:
                captures.append(capture_current_screen(emulator, targets_by_turn[turn], scale))
                if len(captures) == len(CAPTURE_TARGETS):
                    break

            action = str(row.get("action") or "").strip().lower()
            if not action:
                raise RuntimeError(f"Trace row {turn} has no action")

            executor.execute(
                action,
                precise=precise_for_row(row, action),
                settle_frames_override=settle_override_for_row(config, row, action),
            )

            if index + 1 < len(timeline):
                next_expected = row_position(timeline[index + 1])
                force_advance_to_next_row(
                    emulator,
                    memory_reader,
                    executor,
                    config,
                    row,
                    next_expected,
                    direction_retries=direction_retries,
                )

        if len(captures) != len(CAPTURE_TARGETS):
            missing = [
                target.key
                for target in CAPTURE_TARGETS
                if target.key not in {row["key"] for row in captures}
            ]
            raise RuntimeError(f"Did not capture all targets. Missing: {missing}")

        return captures
    finally:
        emulator.stop()


def write_manifest(trace_path: Path, checkpoint_path: Path, captures: Iterable[Dict[str, object]]) -> None:
    payload = {
        "source_trace": str(trace_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "source_checkpoint": str(checkpoint_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "captures": list(captures),
    }
    MANIFEST_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    load_dotenv()
    apply_env_aliases()
    args = parse_args()

    trace_path = Path(args.trace).resolve()
    checkpoint_path = Path(args.checkpoint).resolve()
    ensure_capture_dirs()

    trace = load_trace(trace_path)
    captures = replay_and_capture(
        trace=trace,
        checkpoint_path=checkpoint_path,
        scale=args.scale,
        direction_retries=args.direction_retries,
    )
    write_manifest(trace_path, checkpoint_path, captures)

    print(f"Saved {len(captures)} curated gameplay screenshots.")
    for capture in captures:
        print(f"- {capture['figure_path']} (turn {capture['turn']})")
    print(f"Manifest: {MANIFEST_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
