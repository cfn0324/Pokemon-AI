"""Capture updated desktop and mobile dashboard screenshots with headless Edge."""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import PokemonAIAgent
from src.utils.config import get_config
from src.utils.env import apply_env_aliases


DESKTOP_OUTPUT = PROJECT_ROOT / "docs" / "img" / "2026-04-05" / "main_figures" / "fig01_dashboard_desktop.png"
MOBILE_OUTPUT = PROJECT_ROOT / "docs" / "img" / "2026-04-05" / "main_figures" / "fig02_dashboard_mobile.png"
LEGACY_DESKTOP_OUTPUT = PROJECT_ROOT / "docs" / "img" / "2026-04-05" / "dashboard_preview.png"
LEGACY_MOBILE_OUTPUT = PROJECT_ROOT / "docs" / "img" / "2026-04-05" / "dashboard_preview_mobile.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture dashboard screenshots.")
    parser.add_argument("--port", type=int, default=5010, help="Temporary dashboard port.")
    parser.add_argument("--checkpoint", default="checkpoint_195913", help="Checkpoint to show on the dashboard.")
    parser.add_argument("--wait-seconds", type=float, default=4.0, help="Seconds to wait before capture.")
    return parser.parse_args()


def ensure_parent_dirs() -> None:
    for path in [
        DESKTOP_OUTPUT,
        MOBILE_OUTPUT,
        LEGACY_DESKTOP_OUTPUT,
        LEGACY_MOBILE_OUTPUT,
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)


def find_edge() -> str:
    candidates = [
        shutil.which("msedge.exe"),
        shutil.which("msedge"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise FileNotFoundError("Microsoft Edge executable not found.")


def capture_with_edge(
    edge_exe: str,
    url: str,
    output_path: Path,
    width: int,
    height: int,
) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=edge_exe,
            headless=True,
            args=[
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-sync",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        try:
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
            )
            try:
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(5000)
                page.screenshot(path=str(output_path), full_page=True)
            finally:
                context.close()
        finally:
            browser.close()


def main() -> int:
    load_dotenv()
    apply_env_aliases()
    args = parse_args()

    ensure_parent_dirs()
    edge_exe = find_edge()

    config = get_config()
    config.set("game.headless", True)
    config.set("game.speed", 0)
    config.set("visualization.port", int(args.port))
    config.set("game.prompt_for_checkpoint_on_start", False)
    config.set("game.auto_resume_latest_checkpoint", False)
    config.set("game.resume_checkpoint", str(args.checkpoint))

    agent = PokemonAIAgent()
    url = f"http://127.0.0.1:{args.port}"

    try:
        time.sleep(max(0.5, float(args.wait_seconds)))
        capture_with_edge(edge_exe, url, DESKTOP_OUTPUT, width=1600, height=2200)
        capture_with_edge(edge_exe, url, MOBILE_OUTPUT, width=430, height=2200)
        shutil.copy2(DESKTOP_OUTPUT, LEGACY_DESKTOP_OUTPUT)
        shutil.copy2(MOBILE_OUTPUT, LEGACY_MOBILE_OUTPUT)
    finally:
        agent._shutdown()

    print(f"Saved {DESKTOP_OUTPUT.relative_to(PROJECT_ROOT)}")
    print(f"Saved {MOBILE_OUTPUT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
