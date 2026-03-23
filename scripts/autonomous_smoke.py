"""Run a short autonomous checkpoint smoke test and emit a compact JSON report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import get_config
from src.utils.env import apply_env_aliases


def _simplify_state(state: Dict[str, Any] | None) -> Dict[str, Any]:
    """Reduce the full runtime state to report-friendly fields."""
    state = state or {}
    memory = state.get("memory", {}) or {}
    position = memory.get("position", {}) or {}

    return {
        "turn": state.get("turn"),
        "timestamp": state.get("timestamp"),
        "position": {
            "map_id": position.get("map_id"),
            "x": position.get("x"),
            "y": position.get("y"),
        },
        "badges": memory.get("badge_count", 0),
        "money": memory.get("money", 0),
        "party_size": len(memory.get("party", []) or []),
        "party": memory.get("party", []) or [],
        "in_battle": memory.get("in_battle", False),
        "pre_world": state.get("pre_world", False),
        "pre_starter_script": state.get("pre_starter_script", False),
        "visual": state.get("visual", {}) or {},
        "exploration": {
            "current_map": (state.get("map_memory", {}) or {}).get("current_map"),
            "explored_tiles": (state.get("map_memory", {}) or {}).get("explored_tiles", 0),
            "total_tiles": (state.get("map_memory", {}) or {}).get("total_tiles", 0),
            "exploration_percent": (state.get("map_memory", {}) or {}).get("exploration_percent", 0.0),
        },
        "navigation": state.get("navigation", {}) or {},
        "deltas": state.get("deltas", {}) or {},
    }


def _build_timeline(agent: Any, start_turn: int) -> List[Dict[str, Any]]:
    """Return a compact action timeline for the just-finished smoke window."""
    timeline: List[Dict[str, Any]] = []
    for turn in agent.main_agent.context.recent_turns:
        if turn.turn_number < start_turn:
            continue

        state = turn.state or {}
        memory = state.get("memory", {}) or {}
        position = memory.get("position", {}) or {}
        timeline.append(
            {
                "turn": turn.turn_number,
                "action": turn.action,
                "reasoning": turn.reasoning,
                "result": turn.result,
                "decision_source": turn.decision_source,
                "decision_path": turn.decision_path,
                "screen_type": (
                    turn.screen_type
                    or (state.get("visual", {}) or {}).get("screen_type")
                    or (state.get("visual", {}) or {}).get("ram_screen_type")
                ),
                "observed_screen_type": (
                    (state.get("visual", {}) or {}).get("screen_type")
                    or (state.get("visual", {}) or {}).get("ram_screen_type")
                ),
                "phase_hint": state.get("phase_hint"),
                "position": {
                    "map_id": position.get("map_id"),
                    "x": position.get("x"),
                    "y": position.get("y"),
                },
                "party_size": len(memory.get("party", []) or []),
            }
        )
    return timeline


def _count_by_key(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    """Count timeline rows by a string key."""
    counts: Dict[str, int] = {}
    for row in rows:
        label = str(row.get(key) or "unknown")
        counts[label] = counts.get(label, 0) + 1
    return counts


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    apply_env_aliases()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--turns", type=int, default=40, help="Number of turns to run from the restored checkpoint.")
    parser.add_argument(
        "--checkpoint",
        default="latest",
        help="Checkpoint name to load after startup. Defaults to latest.",
    )
    parser.add_argument(
        "--output",
        default="tmp/autonomous_smoke_report.json",
        help="Path to the JSON report.",
    )
    parser.add_argument(
        "--pure-llm",
        action="store_true",
        help="Disable deterministic control stages and test the run in pure-LLM mode.",
    )
    parser.add_argument(
        "--reset-context",
        action="store_true",
        help="Clear saved recent-turn context after loading the checkpoint.",
    )
    args = parser.parse_args()

    config = get_config()
    config.set("visualization.enabled", False)
    config.set("logging.save_screenshots", False)
    config.set("testing.max_turns", 0)
    config.set("testing.write_checkpoints", False)
    config.set("game.headless", True)
    config.set("game.speed", 0)
    config.set("game.auto_resume_latest_checkpoint", False)
    config.set("game.resume_checkpoint", None)
    config.set("performance.async_decisions", False)
    config.set("progress.checkpoint_interval", 10**9)

    if args.pure_llm:
        config.set("decision.pure_llm_mode", True)
        config.set("decision.retry_same_turn_on_ai_error", True)
        config.set("decision.same_turn_retry_max_attempts", 30)
        config.set("decision.same_turn_retry_timeout_seconds", 45)
        config.set("decision.same_turn_retry_min_delay_seconds", 0.25)
        config.set("ai.guidance_interval_turns", 0)
        config.set("ai.agents.main.temperature", 0.0)
        config.set("ai.decision_max_tokens", 256)
        config.set("ai.api_error_cooldown_seconds", 1)
        config.set("ai.api_error_cooldown_max_seconds", 2)

    requested_turns = max(1, int(args.turns))
    print(
        "[autonomous_smoke] Headless smoke mode is active. "
        "Live dashboard updates are disabled (visualization.enabled=False, game.headless=True)."
    )
    print(
        "[autonomous_smoke] This mode is expected to finish quickly after the requested turn budget. "
        "Run `python main.py` if you want the live dashboard, stream, and model status."
    )
    print(
        f"[autonomous_smoke] checkpoint={args.checkpoint!r}, turns={requested_turns}, "
        f"pure_llm={args.pure_llm}, reset_context={args.reset_context}"
    )

    from main import PokemonAIAgent

    agent = PokemonAIAgent()
    if args.checkpoint and str(args.checkpoint).strip():
        agent._load_checkpoint(str(args.checkpoint), pause_after_load=False)
    if args.reset_context:
        agent.main_agent.context.clear()

    start_turn = int(agent.turn_count)
    agent.max_turns = start_turn + requested_turns
    agent.run()

    latest_checkpoint = None
    checkpoints = agent.get_available_checkpoints(limit=1)
    if checkpoints:
        latest_checkpoint = checkpoints[0]

    final_state = _simplify_state(agent._last_observed_state)
    timeline = _build_timeline(agent, start_turn)
    report = {
        "requested_checkpoint": args.checkpoint,
        "restored_checkpoint": agent._restored_checkpoint_name,
        "pure_llm_mode": bool(args.pure_llm),
        "reset_context": bool(args.reset_context),
        "latest_checkpoint": latest_checkpoint.get("name") if latest_checkpoint else None,
        "start_turn": start_turn,
        "end_turn": int(agent.turn_count),
        "turn_delta": int(agent.turn_count) - start_turn,
        "reached_playable": not bool(final_state.get("pre_world") or final_state.get("pre_starter_script")),
        "api_cooldown_active": agent.main_agent.is_in_api_cooldown(),
        "api_cooldown_remaining": round(agent.main_agent.get_api_cooldown_remaining(), 1),
        "decision_source_counts": _count_by_key(timeline, "decision_source"),
        "decision_path_counts": _count_by_key(timeline, "decision_path"),
        "final_state": final_state,
        "timeline": timeline,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
