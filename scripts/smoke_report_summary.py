"""Aggregate autonomous smoke reports into thesis-friendly summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _load_report(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_ai_control_metrics(report: Dict[str, Any]) -> Dict[str, Any]:
    """Read AI-control metrics, falling back to older report fields when needed."""
    metrics = report.get("ai_control_metrics", {}) or {}
    source_counts = report.get("decision_source_counts", {}) or {}
    path_counts = report.get("decision_path_counts", {}) or {}

    total_turns = int(
        metrics.get("total_turns")
        or report.get("timeline_length")
        or report.get("turn_delta")
        or 0
    )
    main_model_turns = int(metrics.get("main_model_turns", source_counts.get("ai", 0) or 0))
    ai_plan_turns = int(metrics.get("ai_plan_turns", source_counts.get("cached_ai_plan", 0) or 0))
    ai_authored_turns = int(metrics.get("ai_authored_turns", main_model_turns + ai_plan_turns))
    fallback_turns = int(metrics.get("fallback_turns", path_counts.get("fallback", 0) or 0))
    tool_turns = int(path_counts.get("tool", 0) or 0)
    deterministic_tool_turns = int(
        metrics.get("deterministic_tool_turns", max(0, tool_turns - ai_plan_turns))
    )

    def _ratio(name: str, value: int) -> float | None:
        if metrics.get(name) is not None:
            return float(metrics[name])
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
        "main_model_ratio": _ratio("main_model_ratio", main_model_turns),
        "ai_authored_ratio": _ratio("ai_authored_ratio", ai_authored_turns),
        "deterministic_tool_ratio": _ratio("deterministic_tool_ratio", deterministic_tool_turns),
        "fallback_ratio": _ratio("fallback_ratio", fallback_turns),
        "ai_dominant": bool(
            metrics.get(
                "ai_dominant",
                total_turns > 0
                and ai_authored_turns > deterministic_tool_turns
                and ai_authored_turns > fallback_turns,
            )
        ),
    }


def _describe_mode(report: Dict[str, Any]) -> str:
    """Return a compact run-mode label for thesis tables."""
    if report.get("pure_llm_mode"):
        return "pure-llm"
    if report.get("llm_primary_mode") and report.get("ai_full_control_mode"):
        return "llm-primary+ai-full"
    if report.get("llm_primary_mode"):
        return "llm-primary"
    if report.get("ai_full_control_mode"):
        return "ai-full"
    return "default"


def _summarize_report(path: Path, report: Dict[str, Any]) -> Dict[str, Any]:
    final_state = report.get("final_state", {}) or {}
    position = final_state.get("position", {}) or {}
    visual = final_state.get("visual", {}) or {}
    markers = report.get("story_markers", {}) or {}
    validation = report.get("report_validation", {}) or {}
    ai_control = _extract_ai_control_metrics(report)

    highest_level = 0
    for member in final_state.get("party", []) or []:
        try:
            highest_level = max(highest_level, int((member or {}).get("level", 0) or 0))
        except (TypeError, ValueError, AttributeError):
            continue

    return {
        "report_name": path.name,
        "report_path": str(path),
        "checkpoint": report.get("restored_checkpoint") or report.get("requested_checkpoint"),
        "turn_delta": int(report.get("turn_delta", 0) or 0),
        "completed_requested_turns": bool(report.get("completed_requested_turns")),
        "fatal_error": report.get("fatal_error"),
        "final_map": position.get("map_id"),
        "final_x": position.get("x"),
        "final_y": position.get("y"),
        "final_screen": visual.get("screen_type"),
        "final_in_battle": bool(final_state.get("in_battle")),
        "highest_party_level": highest_level,
        "got_pokedex": bool(markers.get("got_pokedex")),
        "delivered_oaks_parcel": bool(markers.get("delivered_oaks_parcel")),
        "started_post_pokedex_departure": bool(markers.get("started_post_pokedex_departure")),
        "reached_route2": bool(markers.get("reached_route2")),
        "reached_viridian_forest": bool(markers.get("reached_viridian_forest")),
        "mode": _describe_mode(report),
        "llm_primary_mode": bool(report.get("llm_primary_mode")),
        "ai_full_control_mode": bool(report.get("ai_full_control_mode")),
        "pure_llm_mode": bool(report.get("pure_llm_mode")),
        "timeline_valid": bool(
            validation.get("timeline_turns_monotonic")
            and validation.get("final_state_matches_end_turn")
            and validation.get("timeline_last_turn_matches_end_turn")
        ),
        "main_model_turns": ai_control["main_model_turns"],
        "ai_plan_turns": ai_control["ai_plan_turns"],
        "ai_authored_turns": ai_control["ai_authored_turns"],
        "deterministic_tool_turns": ai_control["deterministic_tool_turns"],
        "fallback_turns": ai_control["fallback_turns"],
        "main_model_ratio": ai_control["main_model_ratio"],
        "ai_authored_ratio": ai_control["ai_authored_ratio"],
        "deterministic_tool_ratio": ai_control["deterministic_tool_ratio"],
        "fallback_ratio": ai_control["fallback_ratio"],
        "ai_dominant": ai_control["ai_dominant"],
        "decision_source_counts": report.get("decision_source_counts", {}) or {},
        "decision_path_counts": report.get("decision_path_counts", {}) or {},
    }


def _aggregate_rows(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(rows)
    ai_authored_ratios = [
        float(row["ai_authored_ratio"])
        for row in rows
        if row.get("ai_authored_ratio") is not None
    ]
    main_model_ratios = [
        float(row["main_model_ratio"])
        for row in rows
        if row.get("main_model_ratio") is not None
    ]
    return {
        "report_count": len(rows),
        "completed_count": sum(1 for row in rows if row.get("completed_requested_turns")),
        "fatal_error_count": sum(1 for row in rows if row.get("fatal_error")),
        "timeline_valid_count": sum(1 for row in rows if row.get("timeline_valid")),
        "got_pokedex_count": sum(1 for row in rows if row.get("got_pokedex")),
        "reached_route2_count": sum(1 for row in rows if row.get("reached_route2")),
        "reached_viridian_forest_count": sum(1 for row in rows if row.get("reached_viridian_forest")),
        "ai_dominant_count": sum(1 for row in rows if row.get("ai_dominant")),
        "ai_full_control_count": sum(1 for row in rows if row.get("ai_full_control_mode")),
        "avg_ai_authored_ratio": round(sum(ai_authored_ratios) / len(ai_authored_ratios), 4)
        if ai_authored_ratios
        else None,
        "avg_main_model_ratio": round(sum(main_model_ratios) / len(main_model_ratios), 4)
        if main_model_ratios
        else None,
        "max_party_level": max((int(row.get("highest_party_level", 0) or 0) for row in rows), default=0),
    }


def _render_markdown(rows: List[Dict[str, Any]], aggregate: Dict[str, Any]) -> str:
    avg_ai_ratio = aggregate.get("avg_ai_authored_ratio")
    avg_main_model_ratio = aggregate.get("avg_main_model_ratio")
    lines = [
        "# Smoke Report Summary",
        "",
        f"- Reports: {aggregate['report_count']}",
        f"- Completed requested turns: {aggregate['completed_count']}",
        f"- Fatal errors: {aggregate['fatal_error_count']}",
        f"- Timeline-valid reports: {aggregate['timeline_valid_count']}",
        f"- Reports reaching Pokedex: {aggregate['got_pokedex_count']}",
        f"- Reports reaching Route 2: {aggregate['reached_route2_count']}",
        f"- Reports reaching Viridian Forest: {aggregate['reached_viridian_forest_count']}",
        f"- AI-dominant reports: {aggregate['ai_dominant_count']}",
        f"- AI-full-control reports: {aggregate['ai_full_control_count']}",
        f"- Avg AI-authored ratio: {avg_ai_ratio if avg_ai_ratio is not None else 'n/a'}",
        f"- Avg main-model ratio: {avg_main_model_ratio if avg_main_model_ratio is not None else 'n/a'}",
        f"- Max observed party level: {aggregate['max_party_level']}",
        "",
        "| Report | Mode | AI% | Tool% | Turns | Final Pos | Screen | Pokedex | Route2 | Forest | Fatal | Timeline |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for row in rows:
        final_pos = f"{row.get('final_map')} ({row.get('final_x')},{row.get('final_y')})"
        ai_percent = (
            f"{float(row['ai_authored_ratio']) * 100:.1f}%"
            if row.get("ai_authored_ratio") is not None
            else "n/a"
        )
        tool_percent = (
            f"{float(row['deterministic_tool_ratio']) * 100:.1f}%"
            if row.get("deterministic_tool_ratio") is not None
            else "n/a"
        )
        lines.append(
            "| {report_name} | {mode} | {ai_percent} | {tool_percent} | {turn_delta} | {final_pos} | {final_screen} | {got_pokedex} | {reached_route2} | {reached_viridian_forest} | {fatal_error} | {timeline_valid} |".format(
                report_name=row.get("report_name"),
                mode=row.get("mode"),
                ai_percent=ai_percent,
                tool_percent=tool_percent,
                turn_delta=row.get("turn_delta"),
                final_pos=final_pos,
                final_screen=row.get("final_screen"),
                got_pokedex="yes" if row.get("got_pokedex") else "no",
                reached_route2="yes" if row.get("reached_route2") else "no",
                reached_viridian_forest="yes" if row.get("reached_viridian_forest") else "no",
                fatal_error=row.get("fatal_error") or "none",
                timeline_valid="yes" if row.get("timeline_valid") else "no",
            )
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", help="Smoke report JSON files to summarize.")
    parser.add_argument(
        "--format",
        choices={"json", "markdown"},
        default="markdown",
        help="Output format. Defaults to markdown.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output file. Defaults to stdout only.",
    )
    args = parser.parse_args()

    report_paths = [Path(raw).resolve() for raw in args.reports]
    rows = [_summarize_report(path, _load_report(path)) for path in report_paths]
    aggregate = _aggregate_rows(rows)
    payload = {"aggregate": aggregate, "reports": rows}

    if args.format == "json":
        rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        rendered = _render_markdown(rows, aggregate)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")

    print(rendered)


if __name__ == "__main__":
    main()
