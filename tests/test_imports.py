"""Ensure all top-level modules import cleanly (smoke test)."""

from __future__ import annotations


def test_import_package() -> None:
    import zen_type

    assert zen_type.__version__


def test_import_cli() -> None:
    from zen_type.cli import build_parser

    parser = build_parser()
    ns = parser.parse_args([])
    assert hasattr(ns, "debug")


def test_import_constants() -> None:
    from zen_type.core.constants import Mode, PipelineState

    assert Mode.DICTATE.value == "dictate"
    assert PipelineState.IDLE.value == "idle"


def test_import_settings() -> None:
    from zen_type.config.settings import Settings

    assert Settings is not None


def test_import_settings_window_module() -> None:
    # Import lazily to avoid requiring pywebview at import time in headless tests.
    import importlib

    mod = importlib.import_module("zen_type.settings_window")
    assert hasattr(mod, "SettingsApi")
    assert hasattr(mod, "main")


def test_import_audio_devices() -> None:
    from zen_type.core.audio_devices import LevelMeter, list_input_devices

    assert callable(list_input_devices)
    assert LevelMeter is not None


def test_ui_html_bundled() -> None:
    from pathlib import Path

    import zen_type

    html = Path(zen_type.__file__).parent / "ui" / "settings.html"
    assert html.exists(), f"settings.html missing at {html}"
    content = html.read_text(encoding="utf-8")
    assert "zen-type" in content
