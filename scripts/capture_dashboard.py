"""Capture one PNG per dashboard page with headless Chrome.

Usage: python scripts/capture_dashboard.py [--chrome PATH]
Requires Google Chrome or Chromium and Pillow (installed by `uv sync --extra dev`).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image

PAGES = [("overview", "01_care_gap_overview.png"), ("models", "02_model_tradeoffs.png"),
         ("methods", "03_methods_data_quality.png")]
CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]
WIDTH, TALL = 1280, 4200
BACKGROUND = (246, 247, 249)


def find_chrome(explicit: str | None) -> str:
    for candidate in [explicit, *CANDIDATES]:
        if candidate and (Path(candidate).exists() or shutil.which(candidate)):
            return candidate
    raise SystemExit("Chrome or Chromium not found. Pass --chrome PATH.")


def trim(path: Path) -> None:
    """Crop the empty area under the page content."""
    image = Image.open(path).convert("RGB")
    pixels = image.load()
    assert pixels is not None
    last = 0
    for y in range(image.height - 1, -1, -1):
        if any(pixels[x, y] != BACKGROUND for x in range(0, image.width, 8)):
            last = y
            break
    image.crop((0, 0, image.width, min(image.height, last + 24))).save(path, optimize=True)


def _screenshot(chrome: str, url: str, target: Path, timeout: float = 90.0) -> None:
    """Run headless Chrome and stop it once the PNG is written and stable.

    Chrome's --screenshot flag can leave the process running after the file is complete,
    so completion is detected from the file rather than from process exit.
    """
    target.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as profile:
        process = subprocess.Popen(
            [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             f"--user-data-dir={profile}", f"--window-size={WIDTH},{TALL}",
             "--force-color-profile=srgb", "--virtual-time-budget=4000",
             f"--screenshot={target}", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline, last_size = time.monotonic() + timeout, -1
        try:
            while time.monotonic() < deadline:
                size = target.stat().st_size if target.exists() else 0
                if size > 0 and size == last_size:
                    return
                last_size = size
                if process.poll() is not None:
                    if target.exists() and target.stat().st_size > 0:
                        return
                    raise RuntimeError(f"Chrome exited without writing {target}")
                time.sleep(1.5)
            raise TimeoutError(f"Timed out waiting for {target}")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def capture(chrome: str, html: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for page, name in PAGES:
        target = out_dir / name
        _screenshot(chrome, f"{html.resolve().as_uri()}?theme=light#{page}", target)
        trim(target)
        written.append(target)
    return written


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chrome")
    parser.add_argument("--html", type=Path, default=Path("dashboard/index.html"))
    parser.add_argument("--out", type=Path, default=Path("dashboard/screenshots"))
    args = parser.parse_args()
    for path in capture(find_chrome(args.chrome), args.html, args.out):
        print(path, Image.open(path).size)
