"""Application wiring: settings → pipeline → hotkeys → tray → pywebview settings.

The settings UI is NOT embedded in this process — it's launched as a subprocess
running `python -m zen_type.settings_window` which opens a native pywebview window.
When the window closes the subprocess exits and we reload the (possibly changed)
config.
"""

from __future__ import annotations

import logging
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from zen_type.cli import build_parser
from zen_type.config.settings import Settings
from zen_type.core.constants import Mode, PipelineState
from zen_type.core.hotkey import HotkeyError, HotkeyManager
from zen_type.core.logfile import attach_file_logger, get_log_path
from zen_type.core.overlay import Overlay
from zen_type.core.pipeline import AudioPipeline
from zen_type.core.tray import TrayApp

logger = logging.getLogger(__name__)


MODE_FROM_NAME = {
    "dictate": Mode.DICTATE,
    "transform": Mode.TRANSFORM,
    "ask": Mode.ASK,
}


class App:
    def __init__(self, settings: Settings, open_settings_on_start: bool = True) -> None:
        self.settings = settings
        self.open_settings_on_start = open_settings_on_start
        self.pipeline = AudioPipeline(settings)
        self.hotkeys = HotkeyManager()
        self.tray = TrayApp(
            on_open_settings=self._open_settings_window,
            on_reload=self._reload_hotkeys,
            on_quit=self._request_quit,
            on_open_config_path=self._open_config_path,
        )
        self.overlay = Overlay(
            on_open_settings=self._open_settings_window,
            on_reload=self._reload_hotkeys,
            on_quit=self._request_quit,
            on_open_config_path=self._open_config_path,
        )
        self._stop_event = threading.Event()
        self._settings_proc: subprocess.Popen | None = None
        self._settings_proc_log_fp = None  # file handle for child stdio (closed by waiter)
        self._settings_proc_lock = threading.Lock()

        self.pipeline.add_state_listener(self._on_state_change)
        self.pipeline.add_level_listener(self._on_level_change)

    # ---- Callbacks ----
    def _on_state_change(self, state: PipelineState) -> None:
        self.tray.set_state(state)
        self.overlay.set_state(state)

    def _on_level_change(self, level: float) -> None:
        self.tray.set_level(level)
        self.overlay.set_level(level)

    # ---- Hotkey callbacks ----
    # In push-to-talk mode: press starts, release stops.
    # In toggle mode: each press toggles; release is a no-op.
    def _ptt_press(self, mode: Mode) -> None:
        self.pipeline.start_recording(mode)

    def _ptt_release(self, mode: Mode) -> None:  # noqa: ARG002
        self.pipeline.stop_and_process()

    def _toggle_press(self, mode: Mode) -> None:
        self.pipeline.toggle(mode)

    def _noop_release(self, mode: Mode) -> None:  # noqa: ARG002
        pass

    def _reload_hotkeys(self) -> None:
        self.settings.invalidate()
        logger.info("reloading hotkeys from config")
        self._bind_hotkeys()

    def _request_quit(self) -> None:
        logger.info("quit requested from tray")
        self._stop_event.set()

    def _open_config_path(self) -> None:
        path = self.settings.path
        try:
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", str(path)], check=False)
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path.parent)], check=False)
        except Exception as exc:  # noqa: BLE001
            logger.debug("open_config_path failed: %s", exc)

    def _open_settings_window(self) -> None:
        """Launch the pywebview settings subprocess; reload hotkeys when it exits."""
        with self._settings_proc_lock:
            # If a settings window is already open, just focus it (best-effort: no-op)
            if self._settings_proc is not None and self._settings_proc.poll() is None:
                logger.info("settings window already open")
                return

            if getattr(sys, "frozen", False):
                # Frozen onefile build: re-invoke ourselves with --settings-window
                # (sys.executable is the .exe itself, there is no `python -m`).
                cmd = [
                    sys.executable,
                    "--settings-window",
                    "--config-path",
                    str(self.settings.path),
                ]
            else:
                # Source checkout: use `python -m zen_type.settings_window`.
                cmd = [
                    sys.executable,
                    "-m",
                    "zen_type.settings_window",
                    "--config-path",
                    str(self.settings.path),
                ]
            try:
                # CREATE_NO_WINDOW keeps us from flashing a console
                creationflags = 0
                if sys.platform == "win32":
                    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

                # Tee child stdout/stderr into the shared log file so any
                # pre-Python crash (PyInstaller bootloader, missing DLL,
                # WebView2 runtime missing) still leaves a trace.
                log_path = get_log_path()
                log_path.parent.mkdir(parents=True, exist_ok=True)
                child_log_fp = open(log_path, "a", encoding="utf-8", buffering=1)
                child_log_fp.write(
                    f"\n----- spawning settings child: {cmd} -----\n"
                )
                child_log_fp.flush()
                self._settings_proc = subprocess.Popen(
                    cmd,
                    creationflags=creationflags,
                    stdout=child_log_fp,
                    stderr=child_log_fp,
                )
                # Keep a handle so the waiter thread can close it after exit.
                self._settings_proc_log_fp = child_log_fp
                logger.info(
                    "settings window spawned (pid=%s, log=%s)",
                    self._settings_proc.pid,
                    log_path,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("failed to spawn settings window: %s", exc)
                return

            proc = self._settings_proc

        def _waiter() -> None:
            rc = proc.wait()
            logger.info("settings window closed (exit=%s) — reloading config", rc)
            try:
                self._reload_hotkeys()
            except Exception:
                logger.exception("post-settings reload failed")
            with self._settings_proc_lock:
                if self._settings_proc is proc:
                    self._settings_proc = None
                fp = self._settings_proc_log_fp
                self._settings_proc_log_fp = None
            if fp is not None:
                try:
                    fp.close()
                except Exception:  # noqa: BLE001
                    pass

        threading.Thread(target=_waiter, name="zen-type-settings-waiter", daemon=True).start()

    # ---- Startup ----
    def _bind_hotkeys(self) -> None:
        cfg = self.settings.load()
        hotkey_map = cfg.get("hotkeys", {})
        modes_enabled = cfg.get("modesEnabled", {})
        hotkey_mode = cfg.get("hotkeyMode", "toggle")

        if hotkey_mode == "toggle":
            on_press, on_release = self._toggle_press, self._noop_release
        else:
            on_press, on_release = self._ptt_press, self._ptt_release
        logger.info("hotkey behaviour: %s", hotkey_mode)

        self.hotkeys.unhook_all()
        for name, key in hotkey_map.items():
            if not modes_enabled.get(name, True):
                logger.info("mode %s disabled — skipping", name)
                continue
            if not key or not str(key).strip():
                logger.info("mode %s has no hotkey — skipping", name)
                continue
            mode = MODE_FROM_NAME.get(name)
            if mode is None:
                logger.warning("unknown mode name: %s", name)
                continue
            try:
                self.hotkeys.register(mode, key, on_press, on_release)
            except HotkeyError as exc:
                logger.error("could not bind %s (%s): %s", name, key, exc)

    def _first_run_check(self) -> bool:
        """Return True if any API key is set."""
        keys = self.settings.load().get("apiKeys", {})
        return any(bool(v) for k, v in keys.items() if k != "ollama")

    def run(self) -> int:
        self.tray.start()
        self.overlay.start()

        if self.open_settings_on_start and not self._first_run_check():
            logger.info("no API key found — opening settings window")
            self._open_settings_window()

        self._bind_hotkeys()

        logger.info("zen-type is running. Config: %s", self.settings.path)

        def _sig(signum, frame):  # noqa: ARG001
            logger.info("signal %s received", signum)
            self._stop_event.set()

        try:
            signal.signal(signal.SIGINT, _sig)
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, _sig)
        except (ValueError, OSError):
            pass

        try:
            while not self._stop_event.is_set():
                time.sleep(0.3)
        except KeyboardInterrupt:
            logger.info("keyboard interrupt")

        logger.info("shutting down...")
        self.hotkeys.unhook_all()
        self.overlay.stop()
        self.tray.stop()
        with self._settings_proc_lock:
            if self._settings_proc is not None and self._settings_proc.poll() is None:
                try:
                    self._settings_proc.terminate()
                except Exception:  # noqa: BLE001
                    pass
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    # When the frozen exe re-invokes itself to open settings (because there is
    # no `python -m` available in the onefile bundle), delegate straight to the
    # settings-window entry point and skip the tray/pipeline stack.
    if args.settings_window:
        # File logging is attached inside settings_main() with role=settings-child.
        from zen_type.settings_window import main as settings_main

        extra: list[str] = []
        if args.config_path:
            extra += ["--config-path", args.config_path]
        if args.debug:
            extra.append("--debug")
        return settings_main(extra)

    # Parent (tray app) — attach file logger so we always have a trace.
    try:
        attach_file_logger("parent", debug=args.debug)
    except Exception as exc:  # noqa: BLE001
        # File logging failure must never stop the app.
        logger.warning("could not attach file logger: %s", exc)

    config_path: Path | None = Path(args.config_path) if args.config_path else None
    settings = Settings(path=config_path)
    settings.load()
    logger.info("config file: %s", settings.path)

    # Eagerly touch vocabulary so the bundled seed files get copied into the
    # user's editable %APPDATA% folder on first launch (PyInstaller frozen mode).
    try:
        from zen_type.core.vocabulary import file_paths as _vocab_paths

        logger.info("vocabulary files at: %s", _vocab_paths())
    except Exception as exc:  # noqa: BLE001
        logger.warning("vocabulary init skipped: %s", exc)

    app = App(settings, open_settings_on_start=not args.no_browser)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
