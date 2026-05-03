"""Build zen-type into a single-file Windows exe.

Usage:
    uv run python build.py           # build dist\\zen-type-<version>.exe
    uv run python build.py --debug   # build with console window for log visibility

Requires the ``build`` optional-dependency group:
    uv sync --extra build
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Load project version without importing the whole package (avoids pulling in
# heavy deps just to build).
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from zen_type import __version__  # noqa: E402

APP_NAME = f"zen-type-{__version__}"
SRC = ROOT / "src" / "zen_type"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def _clean() -> None:
    for d in (DIST, BUILD):
        if d.exists():
            shutil.rmtree(d)
    for spec in ROOT.glob("*.spec"):
        spec.unlink()


def build(debug_console: bool = False) -> Path:
    _clean()

    # ``;`` is the Windows separator for PyInstaller's --add-data.
    sep = ";" if sys.platform == "win32" else ":"

    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", APP_NAME,
        f"--add-data=src/zen_type/ui/settings.html{sep}zen_type/ui",
        f"--add-data=src/zen_type/assets{sep}zen_type/assets",
        f"--add-data=refer_doc{sep}refer_doc",
        # Native / data-carrying deps that PyInstaller doesn't always catch:
        "--collect-all", "pywebview",
        "--collect-all", "pystray",
        "--collect-all", "keyboard",
        "--collect-all", "sounddevice",
        "--collect-all", "pyautogui",
        # Pillow's Tk bridge (used by overlay.py for PhotoImage rendering)
        "--hidden-import", "PIL.ImageTk",
        "--hidden-import", "PIL._tkinter_finder",
        "--noconfirm",
        str(SRC / "app.py"),
    ]

    if debug_console:
        # Keep the console window so users can see INFO/DEBUG logs.
        args.insert(3, "--console")
    else:
        args.insert(3, "--noconsole")

    print(">>", " ".join(args))
    subprocess.run(args, check=True)

    exe_path = DIST / f"{APP_NAME}.exe"
    if not exe_path.exists():
        raise RuntimeError(f"expected build output not found: {exe_path}")

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    # Avoid Unicode symbols — Windows cp950 console chokes on them.
    print(f"\n[OK] Built: {exe_path}  ({size_mb:.1f} MB)")
    return exe_path


def main() -> int:
    p = argparse.ArgumentParser(description="Build zen-type.exe")
    p.add_argument("--debug", action="store_true", help="include visible console window")
    args = p.parse_args()
    try:
        build(debug_console=args.debug)
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"\n[FAIL] Build failed (exit {exc.returncode}).", file=sys.stderr)
        return exc.returncode


if __name__ == "__main__":
    sys.exit(main())
