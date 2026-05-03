"""Simple feedback beeps. No-op on non-Windows platforms."""

from __future__ import annotations

import logging
import sys
import threading

logger = logging.getLogger(__name__)


def _beep(frequency: int, duration_ms: int) -> None:
    if sys.platform != "win32":
        return
    try:
        import winsound

        winsound.Beep(frequency, duration_ms)
    except Exception as exc:  # noqa: BLE001
        logger.debug("beep failed: %s", exc)


def _async_beep(frequency: int, duration_ms: int) -> None:
    threading.Thread(
        target=_beep, args=(frequency, duration_ms), daemon=True
    ).start()


def play_start() -> None:
    _async_beep(520, 110)


def play_stop() -> None:
    _async_beep(360, 110)


def play_error() -> None:
    _async_beep(220, 220)
