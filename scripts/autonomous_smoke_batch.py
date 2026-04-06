"""Run repeated autonomous smoke experiments under one fixed protocol."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.smoke_report_summary import (
    _aggregate_rows,
    _load_report,
    _render_markdown,
    _summarize_report,
)
from src.utils.env import apply_env_aliases


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sanitize_label(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return cleaned.strip("._-") or "smoke_batch"


def _build_output_paths(root: Path, label: str) -> Dict[str, Path]:
    return {
        "batch_dir": root / label,
        "summary_markdown": root / label / f"{label}_summary.md",
        "summary_json": root / label / f"{label}_summary.json",
        "manifest": root / label / f"{label}_manifest.json",
    }


def _environment_snapshot(env: Mapping[str, str] | None = None) -> Dict[str, Any]:
    env = env or os.environ
    return {
        "AI_BASE_URL": env.get("AI_BASE_URL"),
        "AI_MODEL": env.get("AI_MODEL"),
        "AI_API_KEY_present": bool(env.get("AI_API_KEY")),
    }


def _protocol_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "checkpoint": args.checkpoint,
        "turns": int(args.turns),
        "runs": int(args.runs),
        "llm_primary": bool(args.llm_primary),
        "pure_llm": bool(args.pure_llm),
        "research_mode": bool(args.research_mode),
        "ai_full_control": args.ai_full_control,
        "disable_runtime_fallbacks": bool(args.disable_runtime_fallbacks),
        "reset_context": bool(args.reset_context),
        "ai_timeout": int(args.ai_timeout),
        "same_turn_budget": int(args.same_turn_budget),
        "decision_max_tokens": int(args.decision_max_tokens),
        "action_plan_max_actions": int(args.action_plan_max_actions),
        "stop_on_failure": bool(args.stop_on_failure),
    }


def _build_smoke_command(args: argparse.Namespace, output_path: Path) -> List[str]:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "autonomous_smoke.py"),
        "--checkpoint",
        str(args.checkpoint),
        "--turns",
        str(int(args.turns)),
        "--output",
        str(output_path),
        "--ai-timeout",
        str(int(args.ai_timeout)),
        "--same-turn-budget",
        str(int(args.same_turn_budget)),
        "--decision-max-tokens",
        str(int(args.decision_max_tokens)),
        "--action-plan-max-actions",
        str(int(args.action_plan_max_actions)),
    ]
    if args.llm_primary:
        command.append("--llm-primary")
    if args.pure_llm:
        command.append("--pure-llm")
    if args.research_mode:
        command.append("--research-mode")
    if args.ai_full_control is True:
        command.append("--ai-full-control")
    elif args.ai_full_control is False:
        command.append("--disable-ai-full-control")
    if args.disable_runtime_fallbacks:
        command.append("--disable-runtime-fallbacks")
    if args.reset_context:
        command.append("--reset-context")
    return command


def _run_smoke_once(
    command: Sequence[str],
    report_path: Path,
    stdout_path: Path,
    stderr_path: Path,
    env: Mapping[str, str],
) -> Dict[str, Any]:
    started_at = _utc_now_iso()
    monotonic_start = time.monotonic()
    completed = subprocess.run(
        list(command),
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=dict(env),
        check=False,
    )
    duration_seconds = round(time.monotonic() - monotonic_start, 3)
    stdout_path.write_text(completed.stdout or "", encoding="utf-8")
    stderr_path.write_text(completed.stderr or "", encoding="utf-8")
    return {
        "started_at_utc": started_at,
        "completed_at_utc": _utc_now_iso(),
        "duration_seconds": duration_seconds,
        "return_code": int(completed.returncode),
        "command": list(command),
        "report_path": str(report_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "report_exists": report_path.exists(),
    }


def _summarize_reports(report_paths: Iterable[Path]) -> Dict[str, Any]:
    rows = [_summarize_report(path, _load_report(path)) for path in report_paths]
    aggregate = _aggregate_rows(rows)
    return {
        "aggregate": aggregate,
        "reports": rows,
        "markdown": _render_markdown(rows, aggregate),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default="latest", help="Checkpoint to restore before each run.")
    parser.add_argument("--turns", type=int, default=120, help="Turns to run in each smoke experiment.")
    parser.add_argument("--runs", type=int, default=3, help="Number of repeated runs to execute.")
    parser.add_argument(
        "--label",
        default="",
        help="Optional label used for the output directory and files.",
    )
    parser.add_argument(
        "--output-root",
        default="tmp/real_ai_batches",
        help="Directory that stores batch subdirectories and raw artifacts.",
    )
    parser.add_argument(
        "--summary-markdown",
        default="",
        help="Optional explicit summary Markdown path.",
    )
    parser.add_argument(
        "--summary-json",
        default="",
        help="Optional explicit summary JSON path.",
    )
    parser.add_argument(
        "--manifest",
        default="",
        help="Optional explicit manifest JSON path.",
    )
    parser.add_argument("--llm-primary", action="store_true", help="Enable llm-primary mode.")
    parser.add_argument("--pure-llm", action="store_true", help="Enable pure-LLM mode.")
    parser.add_argument("--research-mode", action="store_true", help="Enable research mode.")
    parser.add_argument(
        "--disable-runtime-fallbacks",
        action="store_true",
        help="Disable runtime fallback/tool takeover behavior in each smoke run.",
    )
    parser.add_argument(
        "--ai-full-control",
        dest="ai_full_control",
        action="store_true",
        default=None,
        help="Enable AI-full-control mode.",
    )
    parser.add_argument(
        "--disable-ai-full-control",
        dest="ai_full_control",
        action="store_false",
        help="Disable AI-full-control mode.",
    )
    parser.add_argument("--reset-context", action="store_true", help="Clear saved recent-turn context before each run.")
    parser.add_argument("--ai-timeout", type=int, default=25, help="Per-request AI timeout in seconds.")
    parser.add_argument("--same-turn-budget", type=int, default=30, help="Same-turn retry budget in seconds.")
    parser.add_argument("--decision-max-tokens", type=int, default=384, help="Decision max_tokens cap.")
    parser.add_argument(
        "--action-plan-max-actions",
        type=int,
        default=3,
        help="Maximum actions kept from each ACTION_PLAN.",
    )
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop the batch immediately if a smoke process exits non-zero.",
    )
    args = parser.parse_args()

    if int(args.runs) <= 0:
        raise SystemExit("--runs must be greater than zero")
    if args.llm_primary and args.pure_llm:
        raise SystemExit("--llm-primary and --pure-llm cannot be enabled together")

    load_dotenv(PROJECT_ROOT / ".env")
    apply_env_aliases()

    label = _sanitize_label(
        args.label or f"{args.checkpoint}_{args.turns}t_{args.runs}runs_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    root = Path(args.output_root).resolve()
    resolved_paths = _build_output_paths(root, label)
    batch_dir = resolved_paths["batch_dir"]
    batch_dir.mkdir(parents=True, exist_ok=True)

    summary_markdown_path = Path(args.summary_markdown).resolve() if args.summary_markdown else resolved_paths["summary_markdown"]
    summary_json_path = Path(args.summary_json).resolve() if args.summary_json else resolved_paths["summary_json"]
    manifest_path = Path(args.manifest).resolve() if args.manifest else resolved_paths["manifest"]
    summary_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    summary_json_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    environment_info = _environment_snapshot(env)
    protocol = _protocol_from_args(args)
    run_records: List[Dict[str, Any]] = []
    report_paths: List[Path] = []

    print(
        "[autonomous_smoke_batch] "
        f"label={label}, checkpoint={args.checkpoint}, turns={args.turns}, runs={args.runs}, "
        f"llm_primary={args.llm_primary}, pure_llm={args.pure_llm}, "
        f"disable_runtime_fallbacks={args.disable_runtime_fallbacks}, "
        f"ai_full_control={args.ai_full_control}"
    )
    print(
        "[autonomous_smoke_batch] "
        f"batch_dir={batch_dir}, AI_MODEL={environment_info['AI_MODEL']!r}, "
        f"AI_BASE_URL={environment_info['AI_BASE_URL']!r}, "
        f"AI_API_KEY_present={environment_info['AI_API_KEY_present']}"
    )

    for run_index in range(1, int(args.runs) + 1):
        run_name = f"{label}_run{run_index:02d}"
        report_path = batch_dir / f"{run_name}.json"
        stdout_path = batch_dir / f"{run_name}.out"
        stderr_path = batch_dir / f"{run_name}.err"
        command = _build_smoke_command(args, report_path)

        print(f"[autonomous_smoke_batch] starting run {run_index}/{args.runs}: {run_name}")
        run_record = _run_smoke_once(command, report_path, stdout_path, stderr_path, env)
        run_record["run_name"] = run_name
        run_records.append(run_record)

        if report_path.exists():
            report_paths.append(report_path)

        if run_record["return_code"] != 0 and args.stop_on_failure:
            print(
                f"[autonomous_smoke_batch] stopping after {run_name} "
                f"because return_code={run_record['return_code']}"
            )
            break

    summary_payload = _summarize_reports(report_paths)
    summary_markdown_path.write_text(summary_payload["markdown"], encoding="utf-8")
    summary_json_path.write_text(
        json.dumps(
            {
                "batch_label": label,
                "protocol": protocol,
                "environment": environment_info,
                "aggregate": summary_payload["aggregate"],
                "reports": summary_payload["reports"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    manifest = {
        "batch_version": 1,
        "label": label,
        "created_at_utc": run_records[0]["started_at_utc"] if run_records else _utc_now_iso(),
        "completed_at_utc": run_records[-1]["completed_at_utc"] if run_records else _utc_now_iso(),
        "project_root": str(PROJECT_ROOT),
        "python_executable": sys.executable,
        "batch_dir": str(batch_dir),
        "protocol": protocol,
        "environment": environment_info,
        "run_count_requested": int(args.runs),
        "run_count_completed": len(run_records),
        "report_count": len(report_paths),
        "summary_markdown_path": str(summary_markdown_path),
        "summary_json_path": str(summary_json_path),
        "runs": run_records,
        "aggregate": summary_payload["aggregate"],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(summary_payload["markdown"])
    print(f"[autonomous_smoke_batch] summary_markdown={summary_markdown_path}")
    print(f"[autonomous_smoke_batch] summary_json={summary_json_path}")
    print(f"[autonomous_smoke_batch] manifest={manifest_path}")


if __name__ == "__main__":
    main()
