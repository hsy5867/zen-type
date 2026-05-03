"""CLI arg parsing."""

from __future__ import annotations

import argparse

from zen_type import __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zen-type",
        description="AI voice input tool (Groq STT + LLM polish).",
    )
    p.add_argument("--version", action="version", version=f"zen-type {__version__}")
    p.add_argument("--debug", action="store_true", help="enable DEBUG logging")
    p.add_argument(
        "--config-path",
        type=str,
        default=None,
        help="override config.json path",
    )
    p.add_argument(
        "--no-browser",
        action="store_true",
        help="do not auto-open the settings window on first run",
    )
    p.add_argument(
        "--settings-window",
        action="store_true",
        help=(
            "run the settings window only (used internally when the frozen "
            "exe re-invokes itself to open settings in a child process)"
        ),
    )
    return p
