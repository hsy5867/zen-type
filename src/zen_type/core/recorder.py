"""Audio recording using sounddevice — streaming capture into numpy buffer."""

from __future__ import annotations

import io
import logging
import math
import threading
import wave
from typing import TYPE_CHECKING, Callable

from zen_type.core.constants import BLOCK_SIZE, CHANNELS, DTYPE, SAMPLE_RATE

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Push-to-Talk style recorder. Safe to call start/stop repeatedly."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        block_size: int = BLOCK_SIZE,
        device: int | str | None = None,
        on_level: Callable[[float], None] | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = block_size
        self.device = device
        self.on_level = on_level
        self._stream = None
        self._chunks: list = []
        self._lock = threading.Lock()
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    def set_device(self, device: int | str | None) -> None:
        self.device = device

    def start(self) -> None:
        import sounddevice as sd

        with self._lock:
            if self._recording:
                logger.warning("start() called while already recording — ignored")
                return
            self._chunks = []
            self._recording = True

            def callback(indata, frames, time_info, status) -> None:  # noqa: ARG001
                if status:
                    logger.debug("sounddevice status: %s", status)
                if not self._recording:
                    return
                self._chunks.append(indata.copy())
                if self.on_level is not None and indata.size:
                    try:
                        import numpy as np  # local import — avoids cost when no listener

                        samples = indata.astype(np.float32) / 32768.0
                        rms = float(np.sqrt(np.mean(samples * samples)))
                        if rms <= 1e-7:
                            disp = 0.0
                        else:
                            db = 20.0 * math.log10(rms)
                            disp = max(0.0, min(1.0, (db + 60.0) / 60.0))
                        self.on_level(disp)
                    except Exception:  # noqa: BLE001
                        pass

            stream_kwargs = {
                "samplerate": self.sample_rate,
                "channels": self.channels,
                "dtype": DTYPE,
                "blocksize": self.block_size,
                "callback": callback,
            }
            if self.device is not None:
                stream_kwargs["device"] = self.device

            self._stream = sd.InputStream(**stream_kwargs)
            self._stream.start()
            logger.debug("recorder started on device=%s", self.device)

    def stop(self) -> "np.ndarray | None":
        import numpy as np

        with self._lock:
            if not self._recording:
                return None
            self._recording = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("error closing stream: %s", exc)
                self._stream = None

            if not self._chunks:
                logger.warning("no audio captured")
                return None

            audio = np.concatenate(self._chunks, axis=0)
            self._chunks = []
            logger.debug(
                "recorder stopped — %d samples (%.2f s)",
                len(audio),
                len(audio) / self.sample_rate,
            )
            return audio


def audio_to_wav_bytes(
    audio: "np.ndarray",
    sample_rate: int = SAMPLE_RATE,
    channels: int = CHANNELS,
) -> bytes:
    """Convert int16 numpy array to WAV-encoded bytes (for API upload)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()
