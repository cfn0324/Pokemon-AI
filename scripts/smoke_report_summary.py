"""Aggregate autonomous smoke reports into thesis-friendly summaries."""

from __future__ import annotations

import argparse
import json
import math
import statistics
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


def _best_story_progress(markers: Dict[str, Any]) -> str:
    """Return the strongest early-story milestone reached by a report."""
    ordered_milestones = [
        "reached_viridian_forest",
        "reached_route2",
        "started_post_pokedex_departure",
        "got_pokedex",
        "delivered_oaks_parcel",
        "obtained_oaks_parcel",
        "entered_viridian_mart",
        "reached_viridian_city",
        "reached_route1",
        "entered_oaks_lab",
        "got_starter",
        "reached_playable",
    ]
    for milestone in ordered_milestones:
        if markers.get(milestone):
            return milestone
    return "no_progress"


def _summarize_report(path: Path, report: Dict[str, Any]) -> Dict[str, Any]:
    final_state = report.get("final_state", {}) or {}
    position = final_state.get("position", {}) or {}
    visual = final_state.get("visual", {}) or {}
    markers = report.get("story_markers", {}) or {}
    validation = report.get("report_validation", {}) or {}
    ai_control = _extract_ai_control_metrics(report)
    latency = report.get("ai_latency_summary", {}) or {}
    source_counts = report.get("decision_source_counts", {}) or {}

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
        "reached_playable": bool(markers.get("reached_playable")),
        "got_starter": bool(markers.get("got_starter")),
        "reached_route1": bool(markers.get("reached_route1")),
        "reached_viridian_city": bool(markers.get("reached_viridian_city")),
        "entered_viridian_mart": bool(markers.get("entered_viridian_mart")),
        "entered_oaks_lab": bool(markers.get("entered_oaks_lab")),
        "obtained_oaks_parcel": bool(markers.get("obtained_oaks_parcel")),
        "got_pokedex": bool(markers.get("got_pokedex")),
        "delivered_oaks_parcel": bool(markers.get("delivered_oaks_parcel")),
        "started_post_pokedex_departure": bool(markers.get("started_post_pokedex_departure")),
        "reached_route2": bool(markers.get("reached_route2")),
        "reached_viridian_forest": bool(markers.get("reached_viridian_forest")),
        "best_story_progress": _best_story_progress(markers),
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
        "ai_error_turns": int(source_counts.get("ai_error", 0) or 0),
        "ai_cooldown_turns": int(source_counts.get("ai_cooldown", 0) or 0),
        "ai_latency_count": int(latency.get("count", 0) or 0),
        "ai_latency_avg_seconds": latency.get("avg_seconds"),
        "ai_latency_max_seconds": latency.get("max_seconds"),
        "ai_latency_min_seconds": latency.get("min_seconds"),
        "ai_latency_total_seconds": latency.get("total_seconds"),
        "ai_avg_request_count": latency.get("avg_request_count"),
        "environment": report.get("environment", {}) or {},
        "effective_settings": report.get("effective_settings", {}) or {},
    }


def _numeric_stats(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "stdev": None,
            "min": None,
            "max": None,
        }
    return {
        "count": len(values),
        "mean": round(sum(values) / len(values), 4),
        "median": round(statistics.median(values), 4),
        "stdev": round(statistics.stdev(values), 4) if len(values) > 1 else 0.0,
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def _binomial_summary(count: int, total: int) -> Dict[str, Any]:
    if total <= 0:
        return {
            "count": count,
            "total": total,
            "rate": None,
            "ci95_low": None,
            "ci95_high": None,
        }
    rate = count / total
    z = 1.96
    denom = 1 + (z * z) / total
    center = (rate + (z * z) / (2 * total)) / denom
    margin = (
        z
        * math.sqrt((rate * (1 - rate) + (z * z) / (4 * total)) / total)
        / denom
    )
    return {
        "count": count,
        "total": total,
        "rate": round(rate, 4),
        "ci95_low": round(max(0.0, center - margin), 4),
        "ci95_high": round(min(1.0, center + margin), 4),
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
    ai_latency_avgs = [
        float(row["ai_latency_avg_seconds"])
        for row in rows
        if row.get("ai_latency_avg_seconds") is not None
    ]
    ai_error_turns = [int(row.get("ai_error_turns", 0) or 0) for row in rows]
    ai_cooldown_turns = [int(row.get("ai_cooldown_turns", 0) or 0) for row in rows]
    report_count = len(rows)
    reached_route1_count = sum(1 for row in rows if row.get("reached_route1"))
    reached_viridian_city_count = sum(1 for row in rows if row.get("reached_viridian_city"))
    entered_viridian_mart_count = sum(1 for row in rows if row.get("entered_viridian_mart"))
    obtained_oaks_parcel_count = sum(1 for row in rows if row.get("obtained_oaks_parcel"))
    delivered_oaks_parcel_count = sum(1 for row in rows if row.get("delivered_oaks_parcel"))
    got_pokedex_count = sum(1 for row in rows if row.get("got_pokedex"))
    started_post_pokedex_departure_count = sum(
        1 for row in rows if row.get("started_post_pokedex_departure")
    )
    reached_route2_count = sum(1 for row in rows if row.get("reached_route2"))
    reached_viridian_forest_count = sum(1 for row in rows if row.get("reached_viridian_forest"))

    return {
        "report_count": report_count,
        "completed_count": sum(1 for row in rows if row.get("completed_requested_turns")),
        "fatal_error_count": sum(1 for row in rows if row.get("fatal_error")),
        "timeline_valid_count": sum(1 for row in rows if row.get("timeline_valid")),
        "obtained_oaks_parcel_count": obtained_oaks_parcel_count,
        "delivered_oaks_parcel_count": delivered_oaks_parcel_count,
        "got_pokedex_count": got_pokedex_count,
        "started_post_pokedex_departure_count": started_post_pokedex_departure_count,
        "reached_route1_count": reached_route1_count,
        "reached_viridian_city_count": reached_viridian_city_count,
        "entered_viridian_mart_count": entered_viridian_mart_count,
        "reached_route2_count": reached_route2_count,
        "reached_viridian_forest_count": reached_viridian_forest_count,
        "ai_dominant_count": sum(1 for row in rows if row.get("ai_dominant")),
        "ai_full_control_count": sum(1 for row in rows if row.get("ai_full_control_mode")),
        "avg_ai_authored_ratio": round(sum(ai_authored_ratios) / len(ai_authored_ratios), 4)
        if ai_authored_ratios
        else None,
        "avg_main_model_ratio": round(sum(main_model_ratios) / len(main_model_ratios), 4)
        if main_model_ratios
        else None,
        "ai_authored_ratio_stats": _numeric_stats(ai_authored_ratios),
        "main_model_ratio_stats": _numeric_stats(main_model_ratios),
        "ai_latency_avg_seconds_stats": _numeric_stats(ai_latency_avgs),
        "ai_error_turns_stats": _numeric_stats([float(value) for value in ai_error_turns]),
        "ai_cooldown_turns_stats": _numeric_stats([float(value) for value in ai_cooldown_turns]),
        "milestone_statistics": {
            "reached_route1": _binomial_summary(reached_route1_count, report_count),
            "reached_viridian_city": _binomial_summary(reached_viridian_city_count, report_count),
            "entered_viridian_mart": _binomial_summary(entered_viridian_mart_count, report_count),
            "obtained_oaks_parcel": _binomial_summary(obtained_oaks_parcel_count, report_count),
            "got_pokedex": _binomial_summary(got_pokedex_count, report_count),
            "reached_route2": _binomial_summary(reached_route2_count, report_count),
            "reached_viridian_forest": _binomial_summary(reached_viridian_forest_count, report_count),
        },
        "max_party_level": max((int(row.get("highest_party_level", 0) or 0) for row in rows), default=0),
    }


def _render_markdown(rows: List[Dict[str, Any]], aggregate: Dict[str, Any]) -> str:
    avg_ai_ratio = aggregate.get("avg_ai_authored_ratio")
    avg_main_model_ratio = aggregate.get("avg_main_model_ratio")
    ai_ratio_stats = aggregate.get("ai_authored_ratio_stats", {}) or {}
    main_ratio_stats = aggregate.get("main_model_ratio_stats", {}) or {}
    latency_stats = aggregate.get("ai_latency_avg_seconds_stats", {}) or {}
    milestone_stats = aggregate.get("milestone_statistics", {}) or {}

    def _resolve_milestone(name: str, count_key: str) -> Dict[str, Any]:
        stats = milestone_stats.get(name, {}) or {}
        if stats:
            return stats
        return _binomial_summary(
            int(aggregate.get(count_key, 0) or 0),
            int(aggregate.get("report_count", 0) or 0),
        )

    route1_stats = _resolve_milestone("reached_route1", "reached_route1_count")
    viridian_city_stats = _resolve_milestone("reached_viridian_city", "reached_viridian_city_count")
    viridian_mart_stats = _resolve_milestone("entered_viridian_mart", "entered_viridian_mart_count")
    parcel_stats = _resolve_milestone("obtained_oaks_parcel", "obtained_oaks_parcel_count")

    def _fmt_rate(stats: Dict[str, Any]) -> str:
        if stats.get("rate") is None:
            return "n/a"
        return (
            f"{stats['count']}/{stats['total']} "
            f"({stats['rate'] * 100:.1f}%, 95% CI {stats['ci95_low'] * 100:.1f}%-{stats['ci95_high'] * 100:.1f}%)"
        )

    lines = [
        "# Smoke Report Summary",
        "",
        f"- Reports: {aggregate['report_count']}",
        f"- Completed requested turns: {aggregate['completed_count']}",
        f"- Fatal errors: {aggregate['fatal_error_count']}",
        f"- Timeline-valid reports: {aggregate['timeline_valid_count']}",
        f"- Reports reaching Route 1: {_fmt_rate(route1_stats)}",
        f"- Reports reaching Viridian City: {_fmt_rate(viridian_city_stats)}",
        f"- Reports entering Viridian Mart: {_fmt_rate(viridian_mart_stats)}",
        f"- Reports obtaining Oak's Parcel: {_fmt_rate(parcel_stats)}",
        f"- Reports delivering Oak's Parcel: {aggregate['delivered_oaks_parcel_count']}",
        f"- Reports reaching Pokedex: {aggregate['got_pokedex_count']}",
        f"- Reports starting post-Pokedex departure: {aggregate['started_post_pokedex_departure_count']}",
        f"- Reports reaching Route 2: {aggregate['reached_route2_count']}",
        f"- Reports reaching Viridian Forest: {aggregate['reached_viridian_forest_count']}",
        f"- AI-dominant reports: {aggregate['ai_dominant_count']}",
        f"- AI-full-control reports: {aggregate['ai_full_control_count']}",
        f"- Avg AI-authored ratio: {avg_ai_ratio if avg_ai_ratio is not None else 'n/a'}",
        f"- Avg main-model ratio: {avg_main_model_ratio if avg_main_model_ratio is not None else 'n/a'}",
        f"- AI-authored ratio median/stdev: {ai_ratio_stats.get('median', 'n/a')} / {ai_ratio_stats.get('stdev', 'n/a')}",
        f"- Main-model ratio median/stdev: {main_ratio_stats.get('median', 'n/a')} / {main_ratio_stats.get('stdev', 'n/a')}",
        f"- AI latency avg median/stdev (s): {latency_stats.get('median', 'n/a')} / {latency_stats.get('stdev', 'n/a')}",
        f"- Max observed party level: {aggregate['max_party_level']}",
        "",
        "| Report | Mode | Progress | AI% | Main% | Tool% | AI avg s | AI err | Cooldown | Turns | Final Pos | Screen | Fatal | Timeline |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |",
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
        main_percent = (
            f"{float(row['main_model_ratio']) * 100:.1f}%"
            if row.get("main_model_ratio") is not None
            else "n/a"
        )
        ai_latency = (
            f"{float(row['ai_latency_avg_seconds']):.3f}"
            if row.get("ai_latency_avg_seconds") is not None
            else "n/a"
        )
        lines.append(
            "| {report_name} | {mode} | {best_story_progress} | {ai_percent} | {main_percent} | {tool_percent} | {ai_latency} | {ai_error_turns} | {ai_cooldown_turns} | {turn_delta} | {final_pos} | {final_screen} | {fatal_error} | {timeline_valid} |".format(
                report_name=row.get("report_name"),
                mode=row.get("mode"),
                best_story_progress=row.get("best_story_progress"),
                ai_percent=ai_percent,
                main_percent=main_percent,
                tool_percent=tool_percent,
                ai_latency=ai_latency,
                ai_error_turns=row.get("ai_error_turns", 0),
                ai_cooldown_turns=row.get("ai_cooldown_turns", 0),
                turn_delta=row.get("turn_delta"),
                final_pos=final_pos,
                final_screen=row.get("final_screen"),
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
