"""Core business pipeline: record → STT → LLM → inject.

State machine:
    IDLE → RECORDING → TRANSCRIBING → POLISHING → INJECTING → IDLE

A single pipeline instance can only process one recording at a time; subsequent
start_recording() calls while busy are ignored (with a warning).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from zen_type.core.constants import MIN_RECORDING_SECONDS, SAMPLE_RATE, Mode, PipelineState
from zen_type.core.context import detect_context_key
from zen_type.core.injector import TextInjector
from zen_type.core.llm import LLMProcessor
from zen_type.core.recorder import AudioRecorder
from zen_type.core.sounds import play_error, play_start, play_stop
from zen_type.core.stt import SpeechToText, STTError

logger = logging.getLogger(__name__)


StateListener = Callable[[PipelineState], None]
LevelListener = Callable[[float], None]


class AudioPipeline:
    def __init__(self, settings, injector: TextInjector | None = None) -> None:
        self.settings = settings
        device = settings.load().get("audioInputDevice")
        self.recorder = AudioRecorder(device=device, on_level=self._emit_level)
        self.stt = SpeechToText(settings)
        self.llm = LLMProcessor(settings)
        self._injector = injector  # may be None → lazy build per call from cfg
        self._state = PipelineState.IDLE
        self._state_lock = threading.Lock()
        self._busy = threading.Event()
        self._listeners: list[StateListener] = []
        self._level_listeners: list[LevelListener] = []
        self._current_mode: Mode | None = None
        self._record_started_at: float = 0.0

    # ---- State management ----
    def add_state_listener(self, listener: StateListener) -> None:
        self._listeners.append(listener)

    def add_level_listener(self, listener: LevelListener) -> None:
        self._level_listeners.append(listener)

    def _emit_level(self, level: float) -> None:
        for cb in self._level_listeners:
            try:
                cb(level)
            except Exception:
                logger.exception("level listener crashed")

    def _set_state(self, state: PipelineState) -> None:
        with self._state_lock:
            self._state = state
        for cb in self._listeners:
            try:
                cb(state)
            except Exception:
                logger.exception("state listener crashed")

    @property
    def state(self) -> PipelineState:
        return self._state

    # ---- Injection ----
    def _make_injector(self) -> TextInjector:
        if self._injector is not None:
            return self._injector
        cfg = self.settings.load()
        return TextInjector(mode=cfg.get("outputMode", "auto_paste"))

    # ---- Toggle API ----
    def toggle(self, mode: Mode) -> None:
        """Single entry-point for toggle-style hotkeys.

        Tap once → start recording. Tap again → stop + process.
        Ignored while a prior recording is still transcribing / polishing /
        injecting (we're still busy with the last session).
        """
        current = self._state
        if current == PipelineState.IDLE and not self._busy.is_set():
            self.start_recording(mode)
        elif current == PipelineState.RECORDING:
            self.stop_and_process()
        else:
            logger.info(
                "toggle ignored — pipeline is %s (still processing previous session)",
                current.value,
            )

    # ---- Public push-to-talk API ----
    def start_recording(self, mode: Mode) -> None:
        t0 = time.monotonic()
        if self._busy.is_set():
            logger.warning("pipeline busy — ignoring start_recording(%s)", mode.value)
            return

        cfg = self.settings.load()
        # Pick up any device change since last run
        self.recorder.set_device(cfg.get("audioInputDevice"))

        # TRANSFORM mode: capture selection BEFORE recording starts
        self._transform_selection: str = ""
        if mode == Mode.TRANSFORM:
            injector = self._make_injector()
            self._transform_selection = injector.capture_selection()
            if not self._transform_selection:
                logger.info("transform mode: no selection captured — aborting")
                play_error()
                return

        self._current_mode = mode
        self._busy.set()
        self._record_started_at = time.monotonic()

        try:
            self.recorder.start()
        except Exception as exc:  # noqa: BLE001
            logger.error("recorder.start failed: %s", exc)
            self._busy.clear()
            self._set_state(PipelineState.ERROR)
            play_error()
            return

        if cfg.get("playSounds", True):
            play_start()
        self._set_state(PipelineState.RECORDING)
        latency_ms = (time.monotonic() - t0) * 1000
        logger.info("recording started (mode=%s, latency=%.0f ms)", mode.value, latency_ms)

    def stop_and_process(self) -> None:
        if not self._busy.is_set():
            return

        cfg = self.settings.load()
        duration = time.monotonic() - self._record_started_at
        audio = self.recorder.stop()

        if cfg.get("playSounds", True):
            play_stop()

        if audio is None or duration < MIN_RECORDING_SECONDS:
            logger.info("recording too short (%.2fs) — discarded", duration)
            self._reset()
            return

        samples = len(audio)
        logger.info("captured %.2fs (%d samples)", samples / SAMPLE_RATE, samples)

        mode = self._current_mode or Mode.DICTATE
        # Run the rest off the caller thread so hotkey release returns quickly
        threading.Thread(
            target=self._process, args=(audio, mode), name="zen-type-pipeline", daemon=True
        ).start()

    # ---- Pipeline body ----
    def _process(self, audio, mode: Mode) -> None:
        try:
            self._set_state(PipelineState.TRANSCRIBING)
            try:
                raw = self.stt.transcribe(audio)
            except STTError as exc:
                logger.error("STT failed: %s", exc)
                play_error()
                self._set_state(PipelineState.ERROR)
                return

            if not raw:
                logger.info("empty transcription — nothing to do")
                return

            logger.info("STT: %s", raw)

            self._set_state(PipelineState.POLISHING)
            output = self._run_mode(mode, raw)

            if not output:
                logger.info("empty output — nothing to inject")
                return

            self._set_state(PipelineState.INJECTING)
            injector = self._make_injector()
            injector.inject(output)
            logger.info("injected %d chars", len(output))
        except Exception:
            logger.exception("pipeline _process crashed")
            play_error()
            self._set_state(PipelineState.ERROR)
        finally:
            self._reset()

    def _run_mode(self, mode: Mode, raw: str) -> str:
        cfg = self.settings.load()
        context_hint = None
        if cfg.get("contextAware", True):
            key = detect_context_key()
            context_hint = (cfg.get("contextTemplates") or {}).get(key)

        if mode == Mode.DICTATE:
            return self.llm.polish(raw, context_hint=context_hint)
        if mode == Mode.TRANSFORM:
            return self.llm.transform(self._transform_selection, instruction=raw)
        if mode == Mode.ASK:
            return self.llm.ask(raw, context_hint=context_hint)
        logger.error("unknown mode %s", mode)
        return raw

    def _reset(self) -> None:
        self._current_mode = None
        self._transform_selection = ""
        self._busy.clear()
        self._set_state(PipelineState.IDLE)
