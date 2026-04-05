"""Run a short autonomous checkpoint smoke test and emit a compact JSON report."""

from __future__ import annotations

import argparse
import copy
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
        "item_count": memory.get("item_count", 0),
        "party_size": len(memory.get("party", []) or []),
        "party": memory.get("party", []) or [],
        "in_battle": memory.get("in_battle", False),
        "events": memory.get("events", {}) or {},
        "ui": memory.get("ui", {}) or {},
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
        "movement_pattern": state.get("movement_pattern", {}) or {},
        "battle_summary": state.get("battle_summary", {}) or {},
    }


def _collect_visited_map_ids(
    timeline: List[Dict[str, Any]],
    final_state: Dict[str, Any],
) -> List[int]:
    """Return visited map ids in stable appearance order."""
    ordered: List[int] = []

    def _remember(map_id: Any) -> None:
        if map_id is None:
            return
        try:
            normalized = int(map_id)
        except (TypeError, ValueError):
            return
        if normalized not in ordered:
            ordered.append(normalized)

    for row in timeline:
        _remember((row.get("position") or {}).get("map_id"))
    _remember((final_state.get("position") or {}).get("map_id"))
    return ordered


def _derive_story_markers(
    final_state: Dict[str, Any],
    timeline: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Summarize early-game milestone progress for reproducible evaluation."""
    events = final_state.get("events", {}) or {}
    visited_maps = _collect_visited_map_ids(timeline, final_state)
    decision_sources = _count_by_key(timeline, "decision_source")

    highest_level = 0
    for member in final_state.get("party", []) or []:
        try:
            highest_level = max(highest_level, int((member or {}).get("level", 0) or 0))
        except (TypeError, ValueError, AttributeError):
            continue

    return {
        "visited_maps": visited_maps,
        "highest_party_level": highest_level,
        "got_starter": bool(final_state.get("party_size", 0)),
        "reached_playable": not bool(final_state.get("pre_world") or final_state.get("pre_starter_script")),
        "reached_route1": 12 in visited_maps,
        "reached_viridian_city": 1 in visited_maps,
        "entered_viridian_mart": 42 in visited_maps,
        "entered_oaks_lab": 40 in visited_maps,
        "obtained_oaks_parcel": bool(
            events.get("got_oaks_parcel")
            or int(final_state.get("item_count", 0) or 0) > 0
        ),
        "delivered_oaks_parcel": bool(events.get("oak_got_parcel")),
        "got_pokedex": bool(events.get("got_pokedex")),
        "started_post_pokedex_departure": decision_sources.get("post_pokedex_departure", 0) > 0,
        "reached_route2": 13 in visited_maps,
        "reached_viridian_forest_south_gate": 50 in visited_maps,
        "reached_viridian_forest": 51 in visited_maps,
    }


def _build_report_validation(
    final_state: Dict[str, Any],
    timeline: List[Dict[str, Any]],
    end_turn: int,
) -> Dict[str, Any]:
    """Expose basic internal consistency checks for smoke reports."""
    timeline_turns = [
        int(row.get("turn"))
        for row in timeline
        if row.get("turn") is not None
    ]
    final_turn = final_state.get("turn")
    timeline_monotonic = all(
        earlier <= later
        for earlier, later in zip(timeline_turns, timeline_turns[1:])
    )
    return {
        "timeline_first_turn": timeline_turns[0] if timeline_turns else None,
        "timeline_last_turn": timeline_turns[-1] if timeline_turns else None,
        "timeline_turn_count": len(timeline_turns),
        "timeline_turns_monotonic": timeline_monotonic,
        "final_state_turn": final_turn,
        "final_state_matches_end_turn": final_turn == end_turn if final_turn is not None else None,
        "timeline_last_turn_matches_end_turn": timeline_turns[-1] == end_turn if timeline_turns else None,
    }


def _build_timeline(
    agent: Any,
    start_turn: int,
    turns: List[Any] | None = None,
) -> List[Dict[str, Any]]:
    """Return a compact action timeline for the just-finished smoke window."""
    def _turn_value(turn: Any, key: str, default: Any = None) -> Any:
        """Read turn fields from dataclasses, namespaces, or dict-like fixtures."""
        if isinstance(turn, dict):
            return turn.get(key, default)
        return getattr(turn, key, default)

    timeline: List[Dict[str, Any]] = []
    source_turns = turns if turns is not None else agent.main_agent.context.recent_turns
    for turn in source_turns:
        turn_number = _turn_value(turn, "turn_number", 0)
        if turn_number < start_turn:
            continue

        state = _turn_value(turn, "state", {}) or {}
        memory = state.get("memory", {}) or {}
        position = memory.get("position", {}) or {}
        timeline.append(
            {
                "turn": turn_number,
                "action": _turn_value(turn, "action"),
                "reasoning": _turn_value(turn, "reasoning"),
                "result": _turn_value(turn, "result"),
                "decision_source": _turn_value(turn, "decision_source"),
                "decision_path": _turn_value(turn, "decision_path"),
                "model_latency_seconds": _turn_value(turn, "model_latency_seconds"),
                "model_request_count": _turn_value(turn, "model_request_count"),
                "screen_type": (
                    _turn_value(turn, "screen_type")
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


def _install_timeline_collector(agent: Any) -> List[Dict[str, Any]]:
    """Capture every smoke-run decision/result even when context trims old turns."""
    context = agent.main_agent.context
    recorded_turns: List[Dict[str, Any]] = []
    original_add_turn = context.add_turn
    original_update_last_turn_result = context.update_last_turn_result

    def add_turn_with_recording(
        turn_number: int,
        state: Dict[str, Any],
        action: Any = None,
        screen_type: Any = None,
        reasoning: Any = None,
        result: Any = None,
        decision_source: Any = None,
        decision_path: Any = None,
        model_latency_seconds: Any = None,
        model_request_count: Any = None,
    ) -> None:
        original_add_turn(
            turn_number=turn_number,
            state=state,
            action=action,
            screen_type=screen_type,
            reasoning=reasoning,
            result=result,
            decision_source=decision_source,
            decision_path=decision_path,
            model_latency_seconds=model_latency_seconds,
            model_request_count=model_request_count,
        )
        recorded_turns.append(
            {
                "turn_number": turn_number,
                "state": copy.deepcopy(state),
                "action": action,
                "screen_type": screen_type,
                "reasoning": reasoning,
                "result": result,
                "decision_source": decision_source,
                "decision_path": decision_path,
                "model_latency_seconds": model_latency_seconds,
                "model_request_count": model_request_count,
            }
        )

    def update_last_turn_result_with_recording(result: str) -> None:
        original_update_last_turn_result(result)
        cleaned = " ".join((result or "").split()).strip()
        if recorded_turns and cleaned:
            recorded_turns[-1]["result"] = cleaned

    context.add_turn = add_turn_with_recording
    context.update_last_turn_result = update_last_turn_result_with_recording
    return recorded_turns


def _count_by_key(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    """Count timeline rows by a string key."""
    counts: Dict[str, int] = {}
    for row in rows:
        label = str(row.get(key) or "unknown")
        counts[label] = counts.get(label, 0) + 1
    return counts


def _summarize_ai_latency(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize per-turn model latency for real AI decisions."""
    values = [
        float(row["model_latency_seconds"])
        for row in rows
        if row.get("decision_source") == "ai" and row.get("model_latency_seconds") is not None
    ]
    request_counts = [
        int(row["model_request_count"])
        for row in rows
        if row.get("decision_source") == "ai" and row.get("model_request_count") is not None
    ]
    if not values:
        return {
            "count": 0,
            "avg_seconds": None,
            "max_seconds": None,
            "min_seconds": None,
            "total_seconds": 0.0,
            "avg_request_count": None,
        }

    return {
        "count": len(values),
        "avg_seconds": round(sum(values) / len(values), 3),
        "max_seconds": round(max(values), 3),
        "min_seconds": round(min(values), 3),
        "total_seconds": round(sum(values), 3),
        "avg_request_count": round(sum(request_counts) / len(request_counts), 3) if request_counts else None,
    }


def _summarize_ai_control(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Quantify how much of a smoke window stayed under AI-led control."""
    total_turns = len(rows)
    main_model_turns = 0
    ai_plan_turns = 0
    fallback_turns = 0
    tool_turns = 0

    for row in rows:
        source = str(row.get("decision_source") or "").strip().lower()
        path = str(row.get("decision_path") or "").strip().lower()
        if source == "ai":
            main_model_turns += 1
        elif source == "cached_ai_plan":
            ai_plan_turns += 1
        if path == "fallback":
            fallback_turns += 1
        elif path == "tool":
            tool_turns += 1

    ai_authored_turns = main_model_turns + ai_plan_turns
    deterministic_tool_turns = max(0, tool_turns - ai_plan_turns)

    def _ratio(value: int) -> float | None:
        if total_turns <= 0:
            return None
        return round(value / total_turns, 4)

    return {
        "total_turns": total_turns,
        "main_model_turns": main_model_turns,
        "ai_plan_turns": ai_plan_turns,
        "ai_authored_turns": ai_authored_turns,
        "deterministic_tool_turns": deterministic_tool_turns,
        "fallback_turns": fallback_turns,
        "main_model_ratio": _ratio(main_model_turns),
        "ai_authored_ratio": _ratio(ai_authored_turns),
        "deterministic_tool_ratio": _ratio(deterministic_tool_turns),
        "fallback_ratio": _ratio(fallback_turns),
        "ai_dominant": bool(
            total_turns > 0
            and ai_authored_turns > deterministic_tool_turns
            and ai_authored_turns > fallback_turns
        ),
    }


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
        "--llm-primary",
        action="store_true",
        help="Use LLM-primary mode with only minimal deterministic safety stages.",
    )
    parser.add_argument(
        "--pure-llm",
        action="store_true",
        help="Disable deterministic control stages and test the run in pure-LLM mode.",
    )
    parser.add_argument(
        "--research-mode",
        action="store_true",
        help="Keep generic safeguards but disable fixed route-script controllers.",
    )
    parser.add_argument(
        "--ai-full-control",
        dest="ai_full_control",
        action="store_true",
        default=None,
        help="Explicitly enable AI-full-control mode so normal gameplay remains AI-owned and deterministic logic stays safety-only.",
    )
    parser.add_argument(
        "--disable-ai-full-control",
        dest="ai_full_control",
        action="store_false",
        help="Explicitly disable AI-full-control mode for comparison or ablation runs.",
    )
    parser.add_argument(
        "--reset-context",
        action="store_true",
        help="Clear saved recent-turn context after loading the checkpoint.",
    )
    parser.add_argument(
        "--ai-timeout",
        type=int,
        default=25,
        help="Per-request AI timeout in seconds for this smoke run.",
    )
    parser.add_argument(
        "--same-turn-budget",
        type=int,
        default=30,
        help="Same-turn retry time budget in seconds for llm-primary/pure-llm smoke runs.",
    )
    parser.add_argument(
        "--decision-max-tokens",
        type=int,
        default=448,
        help="Decision max_tokens cap for this smoke run.",
    )
    parser.add_argument(
        "--action-plan-max-actions",
        type=int,
        default=3,
        help="Maximum actions to keep from ACTION_PLAN for this smoke run.",
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
    config.set("ai.guidance_interval_turns", 0)
    config.set("ai.request_timeout_seconds", max(1, int(args.ai_timeout)))
    config.set("ai.request_retries", 0)
    config.set("ai.request_retry_backoff_seconds", 0.5)
    config.set("ai.api_error_cooldown_seconds", 1)
    config.set("ai.api_error_cooldown_max_seconds", 2)
    config.set("ai.persistent_api_error_cooldown_seconds", 2)
    config.set("ai.unreachable_api_error_cooldown_seconds", 2)
    config.set(
        "ai.decision_max_tokens",
        min(int(config.get("ai.decision_max_tokens", args.decision_max_tokens) or args.decision_max_tokens), int(args.decision_max_tokens)),
    )
    config.set(
        "ai.action_plan_max_actions",
        min(int(config.get("ai.action_plan_max_actions", args.action_plan_max_actions) or args.action_plan_max_actions), int(args.action_plan_max_actions)),
    )
    config.set("testing.disable_stuck_critique", True)
    if args.ai_full_control is not None:
        config.set("decision.ai_full_control_mode", bool(args.ai_full_control))
    if args.llm_primary:
        config.set("decision.llm_primary_mode", True)
        config.set("decision.llm_primary_action_plan_enabled", True)
        config.set("decision.pure_llm_mode", False)
        config.set("decision.retry_same_turn_on_ai_error", True)
        config.set("decision.same_turn_retry_max_attempts", 8)
        config.set("decision.same_turn_retry_timeout_seconds", max(1, int(args.same_turn_budget)))
        config.set("decision.same_turn_retry_min_delay_seconds", 0.25)
        config.set("ai.request_timeout_seconds", max(1, int(args.ai_timeout)))
        config.set("ai.request_retries", 0)
    if args.research_mode:
        config.set("decision.research_mode", True)

    if args.pure_llm:
        config.set("decision.pure_llm_mode", True)
        config.set("decision.llm_primary_mode", False)
        config.set("decision.ai_full_control_mode", False)
        config.set("decision.retry_same_turn_on_ai_error", True)
        config.set("decision.same_turn_retry_max_attempts", 30)
        config.set("decision.same_turn_retry_timeout_seconds", max(1, int(args.same_turn_budget)))
        config.set("decision.same_turn_retry_min_delay_seconds", 0.25)
        config.set("ai.guidance_interval_turns", 0)
        config.set("ai.agents.main.temperature", 0.0)
        config.set("ai.decision_max_tokens", min(int(args.decision_max_tokens), 256))
        config.set("ai.request_timeout_seconds", max(1, int(args.ai_timeout)))
        config.set("ai.request_retries", 1)
        config.set("ai.request_retry_backoff_seconds", 0.5)
        config.set("ai.api_error_cooldown_seconds", 1)
        config.set("ai.api_error_cooldown_max_seconds", 2)
        config.set("ai.persistent_api_error_cooldown_seconds", 2)
        config.set("ai.unreachable_api_error_cooldown_seconds", 2)

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
        f"llm_primary={args.llm_primary}, pure_llm={args.pure_llm}, research_mode={args.research_mode}, "
        f"ai_full_control={bool(config.get('decision.ai_full_control_mode', False))}, "
        f"reset_context={args.reset_context}, ai_timeout={args.ai_timeout}, "
        f"same_turn_budget={args.same_turn_budget}, decision_max_tokens={args.decision_max_tokens}, "
        f"action_plan_max_actions={args.action_plan_max_actions}"
    )

    from main import PokemonAIAgent

    agent = PokemonAIAgent()
    if args.checkpoint and str(args.checkpoint).strip():
        agent._load_checkpoint(str(args.checkpoint), pause_after_load=False)
    if args.reset_context:
        agent.main_agent.context.clear()
    recorded_turns = _install_timeline_collector(agent)

    start_turn = int(agent.turn_count)
    agent.max_turns = start_turn + requested_turns
    agent.run()

    latest_checkpoint = None
    checkpoints = agent.get_available_checkpoints(limit=1)
    if checkpoints:
        latest_checkpoint = checkpoints[0]

    final_state = _simplify_state(agent._last_observed_state)
    timeline = _build_timeline(agent, start_turn, turns=recorded_turns)
    end_turn = int(agent.turn_count)
    story_markers = _derive_story_markers(final_state, timeline)
    report_validation = _build_report_validation(final_state, timeline, end_turn)
    ai_control_metrics = _summarize_ai_control(timeline)
    report = {
        "report_version": 2,
        "requested_checkpoint": args.checkpoint,
        "restored_checkpoint": agent._restored_checkpoint_name,
        "requested_turns": requested_turns,
        "llm_primary_mode": bool(config.get("decision.llm_primary_mode", False)),
        "ai_full_control_mode": bool(config.get("decision.ai_full_control_mode", False)),
        "pure_llm_mode": bool(config.get("decision.pure_llm_mode", False)),
        "research_mode": bool(config.get("decision.research_mode", False)),
        "reset_context": bool(args.reset_context),
        "effective_settings": {
            "llm_primary_mode": config.get("decision.llm_primary_mode"),
            "ai_full_control_mode": config.get("decision.ai_full_control_mode"),
            "pure_llm_mode": config.get("decision.pure_llm_mode"),
            "research_mode": config.get("decision.research_mode"),
            "ai_timeout_seconds": config.get("ai.request_timeout_seconds"),
            "same_turn_retry_timeout_seconds": config.get("decision.same_turn_retry_timeout_seconds"),
            "decision_max_tokens": config.get("ai.decision_max_tokens"),
            "action_plan_max_actions": config.get("ai.action_plan_max_actions"),
            "llm_primary_action_plan_enabled": config.get("decision.llm_primary_action_plan_enabled"),
        },
        "latest_checkpoint": latest_checkpoint.get("name") if latest_checkpoint else None,
        "start_turn": start_turn,
        "end_turn": end_turn,
        "turn_delta": end_turn - start_turn,
        "completed_requested_turns": end_turn - start_turn >= requested_turns,
        "fatal_error": getattr(agent, "_last_fatal_error", None),
        "timeline_length": len(timeline),
        "reached_playable": not bool(final_state.get("pre_world") or final_state.get("pre_starter_script")),
        "api_cooldown_active": agent.main_agent.is_in_api_cooldown(),
        "api_cooldown_remaining": round(agent.main_agent.get_api_cooldown_remaining(), 1),
        "decision_source_counts": _count_by_key(timeline, "decision_source"),
        "decision_path_counts": _count_by_key(timeline, "decision_path"),
        "ai_control_metrics": ai_control_metrics,
        "ai_latency_summary": _summarize_ai_latency(timeline),
        "story_markers": story_markers,
        "report_validation": report_validation,
        "final_state": final_state,
        "timeline": timeline,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
