"""Checkpoint metadata helpers."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _checkpoint_turn_from_name(name: str) -> int:
    """Extract the numeric turn from a checkpoint directory name."""
    if not name.startswith("checkpoint_"):
        return -1
    try:
        return int(name.split("_", 1)[1])
    except (TypeError, ValueError):
        return -1


def _default_checkpoint_kind(name: str) -> str:
    """Infer a checkpoint kind from the directory name."""
    return "turn" if _checkpoint_turn_from_name(name) >= 0 else "named"


def build_checkpoint_metadata(
    *,
    name: str,
    turn: int,
    current_state: Optional[Dict[str, Any]] = None,
    focus: Optional[str] = None,
    primary_goal: Optional[str] = None,
    label: Optional[str] = None,
    kind: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a compact checkpoint metadata record."""
    state = current_state or {}
    memory = state.get("memory", {}) or {}
    position = memory.get("position", {}) or {}
    party = memory.get("party", []) or []
    visual = state.get("visual", {}) or {}

    return {
        "turn": int(turn),
        "created_at": datetime.now().isoformat(),
        "label": label or f"Turn {int(turn)}",
        "position": {
            "map_id": position.get("map_id"),
            "x": position.get("x"),
            "y": position.get("y"),
        },
        "badges": int(memory.get("badge_count", 0) or 0),
        "party_size": len(party),
        "money": int(memory.get("money", 0) or 0),
        "screen_type": visual.get("screen_type"),
        "focus": focus,
        "primary_goal": primary_goal,
        "kind": kind or _default_checkpoint_kind(name),
        "name": name,
    }


def write_checkpoint_metadata(checkpoint_dir: Path, metadata: Dict[str, Any]) -> Path:
    """Write checkpoint metadata.json and return its path."""
    metadata_path = checkpoint_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metadata_path


def load_checkpoint_metadata(checkpoint_dir: Path) -> Dict[str, Any]:
    """Read checkpoint metadata, falling back to directory-derived fields."""
    metadata_path = checkpoint_dir / "metadata.json"
    fallback_turn = _checkpoint_turn_from_name(checkpoint_dir.name)
    fallback = {
        "turn": fallback_turn if fallback_turn >= 0 else 0,
        "created_at": None,
        "label": checkpoint_dir.name,
        "position": {"map_id": None, "x": None, "y": None},
        "badges": 0,
        "party_size": 0,
        "money": 0,
        "screen_type": None,
        "focus": None,
        "primary_goal": None,
        "kind": _default_checkpoint_kind(checkpoint_dir.name),
        "name": checkpoint_dir.name,
    }
    if not metadata_path.exists():
        return fallback

    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback

    merged = dict(fallback)
    merged.update(data or {})
    merged["name"] = checkpoint_dir.name
    return merged


def list_checkpoints(base_dir: str | Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """List checkpoints sorted from newest turn to oldest."""
    checkpoint_root = Path(base_dir)
    if not checkpoint_root.exists():
        return []

    records: List[Dict[str, Any]] = []
    for entry in checkpoint_root.iterdir():
        if not entry.is_dir():
            continue
        if not (entry / "emulator.state").exists() and not (entry / "metadata.json").exists():
            continue
        turn = _checkpoint_turn_from_name(entry.name)
        metadata = load_checkpoint_metadata(entry)
        metadata["path"] = str(entry)
        metadata["turn"] = int(metadata.get("turn", turn if turn >= 0 else 0) or 0)
        metadata["kind"] = str(metadata.get("kind") or _default_checkpoint_kind(entry.name))
        records.append(metadata)

    records.sort(
        key=lambda item: (
            int(item.get("turn", -1)),
            str(item.get("created_at") or ""),
            str(item.get("name") or ""),
        ),
        reverse=True,
    )
    if limit is not None:
        return records[: max(0, int(limit))]
    return records


def list_startup_checkpoints(
    base_dir: str | Path,
    *,
    recent_turn_limit: int = 8,
) -> List[Dict[str, Any]]:
    """List named checkpoints plus a bounded number of recent turn checkpoints."""
    checkpoints = list_checkpoints(base_dir, limit=None)
    named = [item for item in checkpoints if str(item.get("kind") or "") != "turn"]
    turns = [item for item in checkpoints if str(item.get("kind") or "") == "turn"]

    selected: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in named + turns[: max(0, int(recent_turn_limit))]:
        name = str(item.get("name") or "")
        if not name or name in seen:
            continue
        selected.append(item)
        seen.add(name)
    return selected


def prune_old_checkpoints(base_dir: str | Path, keep_latest: int) -> List[Path]:
    """Delete older checkpoints beyond the latest N and return removed paths."""
    keep_latest = max(0, int(keep_latest))
    checkpoints = [
        item
        for item in list_checkpoints(base_dir)
        if str(item.get("kind") or "") == "turn"
    ]
    if keep_latest == 0:
        doomed = checkpoints
    else:
        doomed = checkpoints[keep_latest:]

    removed: List[Path] = []
    for checkpoint in doomed:
        path = Path(checkpoint["path"])
        if not path.exists():
            continue
        shutil.rmtree(path, ignore_errors=True)
        removed.append(path)
    return removed
