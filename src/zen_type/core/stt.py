"""Speech-to-text via Groq (default) using OpenAI-compatible API."""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

from zen_type.core.constants import DEFAULT_STT_MODEL, GROQ_BASE_URL
from zen_type.core.recorder import audio_to_wav_bytes

if TYPE_CHECKING:
    import numpy as np

    from zen_type.config.settings import Settings

logger = logging.getLogger(__name__)

LANGUAGE_MAP = {
    "auto": None,
    "zh-TW": "zh",
    "zh-CN": "zh",
    "en": "en",
    "ja": "ja",
}


class STTError(Exception):
    """Raised when transcription fails."""


class SpeechToText:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # Groq Whisper caps the ``prompt`` parameter at 896 UTF-8 bytes. We
    # budget below that to stay safe.
    _PROMPT_MAX_BYTES = 850

    def _get_prompt(self, cfg: dict) -> str | None:
        """Build Whisper ``prompt`` parameter — language seed + short vocab.

        Enforces a byte budget (not char budget), because Groq counts the
        UTF-8 byte length and each Traditional-Chinese char is 3 bytes.
        """
        from zen_type.core.vocabulary import byte_len, load_all, pack_terms

        parts: list[str] = []
        language = cfg.get("language", "auto")

        if language == "zh-TW":
            parts.append("以下是繁體中文（台灣）的語音轉錄，請使用繁體字輸出。")
        elif language == "zh-CN":
            parts.append("以下是简体中文的语音转录。")

        chinese_terms, english_terms = load_all()

        used_bytes = sum(byte_len(p) for p in parts) + max(0, len(parts) - 1)
        remaining = max(0, self._PROMPT_MAX_BYTES - used_bytes)

        # 60/40 split between Chinese and English term blocks.
        zh_budget = int(remaining * 0.60)
        en_budget = remaining - zh_budget

        zh_block = pack_terms("常見中文詞彙：", chinese_terms, "、", "。", zh_budget)
        if zh_block:
            parts.append(zh_block)

        en_block = pack_terms("Common terms: ", english_terms, ", ", ".", en_budget)
        if en_block:
            parts.append(en_block)

        if not parts:
            return None

        prompt = " ".join(parts)
        # Final safety clamp on byte length — should never trip with a tiny
        # vocabulary, but keeps us honest if someone expands the lists.
        encoded = prompt.encode("utf-8")
        if len(encoded) > self._PROMPT_MAX_BYTES:
            prompt = encoded[: self._PROMPT_MAX_BYTES].decode("utf-8", errors="ignore")
            logger.warning("Whisper prompt exceeded budget — truncated to %d bytes", self._PROMPT_MAX_BYTES)

        logger.debug(
            "Whisper prompt: %d chars / %d utf-8 bytes",
            len(prompt), len(prompt.encode("utf-8")),
        )
        return prompt

    def transcribe(self, audio: "np.ndarray") -> str:
        cfg = self.settings.load()
        provider = cfg.get("sttProvider", "groq")

        if provider == "groq":
            return self._transcribe_groq(audio, cfg)
        if provider == "openai":
            return self._transcribe_openai(audio, cfg)
        if provider == "local":
            return self._transcribe_local(audio, cfg)
        raise STTError(f"unknown sttProvider: {provider}")

    # ---- Groq ----
    def _transcribe_groq(self, audio: "np.ndarray", cfg: dict) -> str:
        from openai import OpenAI

        api_key = (cfg.get("apiKeys") or {}).get("groq")
        if not api_key:
            raise STTError("Groq API key is not configured")

        model = cfg.get("sttModel") or DEFAULT_STT_MODEL
        language = LANGUAGE_MAP.get(cfg.get("language", "auto"))
        prompt = self._get_prompt(cfg)

        wav_bytes = audio_to_wav_bytes(audio)
        client = OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)

        kwargs = {
            "model": model,
            "file": ("audio.wav", io.BytesIO(wav_bytes), "audio/wav"),
            "response_format": "text",
        }
        if language:
            kwargs["language"] = language
        if prompt:
            kwargs["prompt"] = prompt

        try:
            result = client.audio.transcriptions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise STTError(f"Groq transcription failed: {exc}") from exc

        # result may be a str (response_format=text) or an object with .text
        text = result if isinstance(result, str) else getattr(result, "text", "")
        return (text or "").strip()

    # ---- OpenAI ----
    def _transcribe_openai(self, audio: "np.ndarray", cfg: dict) -> str:
        from openai import OpenAI

        api_key = (cfg.get("apiKeys") or {}).get("openai")
        if not api_key:
            raise STTError("OpenAI API key is not configured")

        model = cfg.get("sttModel") or "whisper-1"
        language = LANGUAGE_MAP.get(cfg.get("language", "auto"))
        prompt = self._get_prompt(cfg)

        wav_bytes = audio_to_wav_bytes(audio)
        client = OpenAI(api_key=api_key)

        kwargs = {
            "model": model,
            "file": ("audio.wav", io.BytesIO(wav_bytes), "audio/wav"),
            "response_format": "text",
        }
        if language:
            kwargs["language"] = language
        if prompt:
            kwargs["prompt"] = prompt

        try:
            result = client.audio.transcriptions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise STTError(f"OpenAI transcription failed: {exc}") from exc

        text = result if isinstance(result, str) else getattr(result, "text", "")
        return (text or "").strip()

    # ---- Local (stub) ----
    def _transcribe_local(self, audio: "np.ndarray", cfg: dict) -> str:  # noqa: ARG002
        raise STTError(
            "Local STT not enabled. Install with: uv sync --extra local, "
            "then set sttProvider='local' and sttModel to a faster-whisper model name."
        )
