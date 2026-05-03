"""Standalone settings window — pywebview native window hosting settings.html.

Runs as its own process (spawned by the tray app), so we never block the main
pipeline or fight pywebview's main-thread requirement. Exits when the window
is closed; the parent app reloads the (possibly changed) config afterwards.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

from zen_type.config.settings import Settings
from zen_type.core.audio_devices import LevelMeter, list_input_devices
from zen_type.core.logfile import attach_file_logger
from zen_type.core.vocabulary import file_paths as vocab_file_paths
from zen_type.core.vocabulary import load_all as vocab_load_all

logger = logging.getLogger(__name__)


def _resolve_html_path() -> Path:
    """Locate ``settings.html`` in both source-checkout and PyInstaller frozen modes.

    Frozen onefile: PyInstaller extracts data files under ``sys._MEIPASS``; the
    spec/build script places ``settings.html`` at ``<_MEIPASS>/zen_type/ui/``.
    Falling back to ``__file__`` is unreliable inside the bundle because the
    module may live in a PYZ archive without a real on-disk filename.

    Source mode: the module file is ``<repo>/src/zen_type/settings_window.py``,
    so its parent (``<repo>/src/zen_type``) plus ``ui/settings.html`` works.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "zen_type" / "ui" / "settings.html"
    return Path(__file__).resolve().parent / "ui" / "settings.html"


HTML_PATH = _resolve_html_path()


class SettingsApi:
    """Exposed to JS as window.pywebview.api.*"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._meter = LevelMeter()

    # ---- Config ----
    def get_config(self) -> dict[str, Any]:
        return self.settings.load()

    def save_config(self, cfg: dict[str, Any]) -> dict[str, Any]:
        self.settings.save(cfg)
        return {"ok": True, "warnings": self.settings.validate()}

    def set_api_key(self, provider: str, key: str) -> dict[str, Any]:
        self.settings.set_api_key(provider, key)
        return {"ok": True}

    def validate(self) -> list[str]:
        return self.settings.validate()

    # ---- Audio devices ----
    def list_audio_devices(self) -> list[dict[str, Any]]:
        return list_input_devices()

    def start_level_meter(self, device: Any = None) -> dict[str, Any]:
        try:
            # pywebview sometimes sends "" for None from empty-string <select>
            if device == "" or device == "null":
                device = None
            if isinstance(device, str) and device.lstrip("-").isdigit():
                device = int(device)
            self._meter.start(device=device)
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def stop_level_meter(self) -> dict[str, Any]:
        self._meter.stop()
        return {"ok": True}

    def get_level(self) -> dict[str, float]:
        return {"level": self._meter.level, "peak": self._meter.peak}

    def reset_peak(self) -> dict[str, bool]:
        self._meter.reset_peak()
        return {"ok": True}

    # ---- Vocabulary (loaded from refer_doc/*.txt) ----
    def get_vocabulary(self) -> dict[str, object]:
        chinese, english = vocab_load_all()
        return {
            "chinese": chinese,
            "english": english,
            "paths": vocab_file_paths(),
        }

    def open_vocab_file(self, which: str) -> dict[str, object]:
        """Open one of the vocabulary files in the user's default text editor.

        ``which`` must be ``"chinese"`` or ``"english"``. Uses the OS "open"
        association: on Windows this launches whatever is registered for
        ``.txt`` (Notepad, VS Code, etc.).
        """
        import os
        import subprocess

        paths = vocab_file_paths()
        target = paths.get(which)
        if not target:
            return {"ok": False, "error": f"unknown file key: {which!r}"}
        if not Path(target).exists():
            return {"ok": False, "error": f"file not found: {target}"}

        try:
            if sys.platform == "win32":
                os.startfile(target)  # noqa: S606 — user-triggered
            elif sys.platform == "darwin":
                subprocess.run(["open", target], check=False)
            else:
                subprocess.run(["xdg-open", target], check=False)
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    # ---- Misc ----
    def open_config_folder(self) -> dict[str, bool]:
        import subprocess

        path = self.settings.path
        try:
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", str(path)], check=False)
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path.parent)], check=False)
            return {"ok": True}
        except Exception:
            return {"ok": False}

    def get_version(self) -> str:
        from zen_type import __version__

        return __version__


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="zen-type settings window")
    p.add_argument("--config-path", type=str, default=None)
    p.add_argument("--debug", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    # Persist a copy to the shared log file so silent --noconsole crashes
    # are still investigable.
    try:
        attach_file_logger("settings-child", debug=args.debug)
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not attach file logger: %s", exc)

    logger.info(
        "settings_window starting: HTML_PATH=%s exists=%s _MEIPASS=%s",
        HTML_PATH,
        HTML_PATH.exists(),
        getattr(sys, "_MEIPASS", None),
    )

    settings = Settings(
        path=Path(args.config_path) if args.config_path else None
    )
    settings.load()  # ensure created
    api = SettingsApi(settings)

    if not HTML_PATH.exists():
        # Dump the bundle layout so we can see exactly what got packaged.
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            base = Path(meipass)
            try:
                listing = sorted(p.relative_to(base).as_posix() for p in base.rglob("*.html"))
                logger.error(
                    "settings.html missing at %s; bundled .html files: %s",
                    HTML_PATH,
                    listing[:50],
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("settings.html missing at %s; rglob failed: %s", HTML_PATH, exc)
        else:
            logger.error("settings.html missing at %s (not frozen)", HTML_PATH)
        return 1

    try:
        import webview  # imported late so non-settings runs stay fast
    except Exception:
        logger.exception("failed to import pywebview")
        return 2

    try:
        window = webview.create_window(
            title="zen-type 設定",
            url=str(HTML_PATH),
            js_api=api,
            width=980,
            height=760,
            min_size=(760, 560),
            resizable=True,
        )

        def _on_closed():
            try:
                api._meter.stop()
            except Exception:  # noqa: BLE001
                pass

        window.events.closed += _on_closed

        webview.start(debug=args.debug)
    except Exception:
        # Most likely culprit: WebView2 Runtime missing on Windows.
        # Letting the exception escape would mean a silent exit under
        # --noconsole; logging it gives us a chance to diagnose.
        logger.exception("webview failed to start")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
