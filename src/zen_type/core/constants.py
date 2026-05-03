"""Centralised constants. Prefer editing via config for user-tunable values."""

from __future__ import annotations

from enum import Enum

# ---- Audio ----
SAMPLE_RATE = 16000  # Hz — Whisper standard
CHANNELS = 1
BLOCK_SIZE = 1024
DTYPE = "int16"
MIN_RECORDING_SECONDS = 0.3

# ---- Injection ----
CLIPBOARD_SETTLE_SECONDS = 0.1
INJECT_DELAY_SECONDS = 0.3

# ---- Settings server ----
SETTINGS_SERVER_HOST = "127.0.0.1"
SETTINGS_SERVER_PORT = 7878

# ---- STT ----
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_STT_MODEL = "whisper-large-v3"

# ---- LLM defaults ----
DEFAULT_LLM_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "ollama": "qwen3:8b",
}

# ---- Hotkey choices ----
VALID_HOTKEYS = {
    "RightAlt",
    "RightCtrl",
    "F9",
    "F10",
    "CapsLock",
    "ScrollLock",
    "Pause",
}

HOTKEY_TO_KEYBOARD_LIB = {
    "RightAlt": "right alt",
    "RightCtrl": "right ctrl",
    "F9": "f9",
    "F10": "f10",
    "CapsLock": "caps lock",
    "ScrollLock": "scroll lock",
    "Pause": "pause",
}

# ---- Provider whitelists ----
VALID_STT_PROVIDERS = {"groq", "openai", "local"}
VALID_LLM_PROVIDERS = {"groq", "openai", "anthropic", "ollama"}
VALID_LANGUAGES = {"auto", "zh-TW", "zh-CN", "en", "ja"}
VALID_OUTPUT_MODES = {"clipboard", "auto_paste"}


class Mode(str, Enum):
    """Pipeline mode — which Push-to-Talk key was pressed."""

    DICTATE = "dictate"      # record → STT → polish → inject
    TRANSFORM = "transform"  # grab selection → record instruction → rewrite → paste back
    ASK = "ask"              # record question → LLM answer → inject


class PipelineState(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    POLISHING = "polishing"
    INJECTING = "injecting"
    ERROR = "error"
