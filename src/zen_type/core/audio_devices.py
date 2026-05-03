"""Audio device enumeration + non-blocking input-level meter.

Used by the settings UI to:
    1. List available input devices
    2. Let the user pick one
    3. Display a live microphone-level bar so they can test the selection
"""

from __future__ import annotations

import logging
import math
import threading
from typing import Any

import numpy as np

from zen_type.core.constants import BLOCK_SIZE, CHANNELS, SAMPLE_RATE

logger = logging.getLogger(__name__)


def list_input_devices() -> list[dict[str, Any]]:
    """Return a list of input-capable audio devices.

    Each entry:
        {
          "index": 3,
          "name": "Microphone (Realtek)",
          "channels": 2,
          "sample_rate": 48000,
          "is_default": True
        }
    """
    try:
        import sounddevice as sd
    except Exception as exc:  # noqa: BLE001
        logger.error("sounddevice import failed: %s", exc)
        return []

    try:
        devices = sd.query_devices()
        default_in = sd.default.device[0] if sd.default.device else None
    except Exception as exc:  # noqa: BLE001
        logger.error("query_devices failed: %s", exc)
        return []

    out: list[dict[str, Any]] = []
    for idx, d in enumerate(devices):
        if d.get("max_input_channels", 0) <= 0:
            continue
        out.append(
            {
                "index": idx,
                "name": d.get("name", f"Device {idx}"),
                "channels": int(d.get("max_input_channels", 0)),
                "sample_rate": int(d.get("default_samplerate", 0)),
                "is_default": idx == default_in,
                "hostapi": int(d.get("hostapi", 0)),
            }
        )
    return out


class LevelMeter:
    """Continuously sample the chosen input device and publish an RMS level.

    Level is normalised to 0.0 – 1.0 (clamped).  Caller polls `level` from the UI.
    """

    def __init__(self) -> None:
        self._stream = None
        self._device: int | str | None = None
        self._level: float = 0.0
        self._peak: float = 0.0
        self._lock = threading.Lock()
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    @property
    def level(self) -> float:
        with self._lock:
            return self._level

    @property
    def peak(self) -> float:
        with self._lock:
            return self._peak

    def reset_peak(self) -> None:
        with self._lock:
            self._peak = 0.0

    def start(self, device: int | str | None = None) -> None:
        import sounddevice as sd

        self.stop()  # clear any previous
        self._device = device

        def callback(indata, frames, time_info, status) -> None:  # noqa: ARG001
            if status:
                logger.debug("level-meter status: %s", status)
            if indata.size == 0:
                return
            # indata is int16 — normalise, compute RMS
            samples = indata.astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(samples * samples)))
            # Map RMS to a perceptual 0..1 scale (log-ish).
            # -60 dBFS → 0.0, 0 dBFS → 1.0
            if rms <= 1e-7:
                disp = 0.0
            else:
                db = 20.0 * math.log10(rms)
                disp = max(0.0, min(1.0, (db + 60.0) / 60.0))
            with self._lock:
                self._level = disp
                if disp > self._peak:
                    self._peak = disp

        kwargs: dict[str, Any] = {
            "samplerate": SAMPLE_RATE,
            "channels": CHANNELS,
            "dtype": "int16",
            "blocksize": BLOCK_SIZE,
            "callback": callback,
        }
        if device is not None:
            kwargs["device"] = device

        try:
            self._stream = sd.InputStream(**kwargs)
            self._stream.start()
            self._running = True
            logger.info("level meter started on device=%s", device)
        except Exception as exc:  # noqa: BLE001
            logger.error("level meter start failed: %s", exc)
            self._stream = None
            self._running = False
            raise

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("level meter stop error: %s", exc)
        self._stream = None
        self._running = False
        with self._lock:
            self._level = 0.0
