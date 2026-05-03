"""JSON-backed settings with schema_version and migration."""

from __future__ import annotations

import copy
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    # STT
    "sttProvider": "groq",
    "sttModel": "whisper-large-v3",
    "language": "auto",
    # LLM
    "llmProvider": "groq",
    "llmModel": "llama-3.3-70b-versatile",
    # API keys
    "apiKeys": {
        "groq": "",
        "openai": "",
        "anthropic": "",
        "ollama": "http://localhost:11434",
    },
    # Multi-mode hotkeys. Only Dictate is enabled by default; Pause single key
    # avoids all Ctrl/Alt/Shift low-level-hook interference with Windows IME
    # and normal typing, and is rarely typed by accident.
    "hotkeys": {
        "dictate": "pause",
        "transform": "",
        "ask": "",
    },
    "modesEnabled": {
        "dictate": True,
        "transform": False,
        "ask": False,
    },
    # "toggle": tap once to start, tap again to stop (hands-free).
    # "push_to_talk": hold to record, release to stop (legacy).
    "hotkeyMode": "toggle",
    # Audio input
    "audioInputDevice": None,  # None = system default; or int device index; or str substring match
    # Output
    "outputMode": "auto_paste",  # "clipboard" | "auto_paste"
    # Behavior
    "autoStart": False,
    "contextAware": True,
    "playSounds": True,
    # Context templates (editable)
    "contextTemplates": {
        "email": "以正式、有禮、結構清晰的書面語整理",
        "chat": "以輕鬆口語、自然對話的語氣整理",
        "code": "技術性、簡潔，保留英文專有名詞與程式符號",
        "doc": "條理分明、標點完整的文件語氣",
        "default": "保留原意，僅整理贅字與標點",
    },
    # Custom vocabulary (improves Whisper accuracy via prompt)
    "dictionary": [],
    # System prompts (user-editable)
    "polishPrompt": (
        "你是一位嚴謹的文字編輯。請整理以下由語音轉錄而來的文字：\n"
        "1) 移除口頭禪（嗯、啊、那個、就是說、然後...）。\n"
        "2) 將口述的「新行/換行/new line」轉為換行符號 \\n；「新段落/new paragraph」轉為兩個 \\n\\n；"
        "口說的「句號/逗號/問號/驚嘆號/冒號」轉為實際標點。\n"
        "3) 修正中英夾雜的空格與大小寫。\n"
        "4) 偵測自我修正時保留最終版本。\n"
        "5) 嚴格保持原意，不擴寫、不總結。\n"
        "只輸出整理後的文字本身，不要任何前言或解釋。"
    ),
    "transformPrompt": (
        "你是一位文字改寫助手。使用者會提供「原始文字」與「改寫指令」，"
        "請依照指令改寫原始文字。只輸出改寫後的結果。"
    ),
    "askPrompt": (
        "你是一位精簡的問答助手。請直接回答問題，不要客套話。"
        "若需要列點，使用精簡的條列式。"
    ),
    "telemetry": False,
}


def get_config_dir() -> Path:
    """Return the config directory (platform-aware)."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "zen-type"
    return Path.home() / ".config" / "zen-type"


def get_config_path() -> Path:
    return get_config_dir() / "config.json"


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override onto a deep copy of base. Missing keys get defaults."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


_LEGACY_HOTKEY_MAP = {
    "RightAlt": "left alt+space",   # new safer default
    "RightCtrl": "left ctrl+space",
    "LeftAlt": "left alt+space",
    "LeftCtrl": "left ctrl+space",
    "F9": "f9",
    "F10": "f10",
    "CapsLock": "caps lock",
    "ScrollLock": "scroll lock",
    "Pause": "pause",
}


def migrate(cfg: dict) -> dict:
    """Apply migrations to bring cfg up to current schema version."""
    # Always: upgrade any Pascal-style hotkey labels to lowercase+combo format.
    hk = cfg.get("hotkeys") or {}
    changed = False
    for name, value in list(hk.items()):
        if isinstance(value, str) and value in _LEGACY_HOTKEY_MAP:
            hk[name] = _LEGACY_HOTKEY_MAP[value]
            changed = True
    if changed:
        cfg["hotkeys"] = hk
        logger.info("Hotkeys migrated to combo format: %s", hk)

    version = cfg.get("schema_version", 0)
    if version == SCHEMA_VERSION:
        return cfg
    cfg["schema_version"] = SCHEMA_VERSION
    logger.info("Config migrated to schema_version=%s", SCHEMA_VERSION)
    return cfg


class Settings:
    """Thread-safe JSON settings store."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_config_path()
        self._lock = threading.RLock()
        self._cache: dict[str, Any] | None = None

    # ---- Core I/O ----
    def load(self) -> dict[str, Any]:
        with self._lock:
            if self._cache is not None:
                return copy.deepcopy(self._cache)

            if not self.path.exists():
                logger.info("No config found at %s — creating defaults.", self.path)
                self._cache = copy.deepcopy(DEFAULT_CONFIG)
                self._save_locked(self._cache)
                return copy.deepcopy(self._cache)

            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.error("Failed to read config (%s); falling back to defaults.", exc)
                self._cache = copy.deepcopy(DEFAULT_CONFIG)
                return copy.deepcopy(self._cache)

            merged = _deep_merge(DEFAULT_CONFIG, raw)
            migrated = migrate(merged)
            if migrated != raw:
                self._save_locked(migrated)
            self._cache = migrated
            return copy.deepcopy(self._cache)

    def save(self, cfg: dict[str, Any]) -> None:
        with self._lock:
            merged = _deep_merge(DEFAULT_CONFIG, cfg)
            self._save_locked(merged)
            self._cache = merged

    def _save_locked(self, cfg: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        logger.debug("Config saved to %s", self.path)

    # ---- Convenience ----
    def get(self, key: str, default: Any = None) -> Any:
        return self.load().get(key, default)

    def set(self, key: str, value: Any) -> None:
        cfg = self.load()
        cfg[key] = value
        self.save(cfg)

    def set_api_key(self, provider: str, key: str) -> None:
        cfg = self.load()
        cfg.setdefault("apiKeys", {})[provider] = key
        self.save(cfg)

    def invalidate(self) -> None:
        with self._lock:
            self._cache = None

    # ---- Validation ----
    def validate(self) -> list[str]:
        """Return a list of human-readable validation errors."""
        from zen_type.core.constants import (
            VALID_LANGUAGES,
            VALID_LLM_PROVIDERS,
            VALID_OUTPUT_MODES,
            VALID_STT_PROVIDERS,
        )

        errors: list[str] = []
        cfg = self.load()

        if cfg.get("sttProvider") not in VALID_STT_PROVIDERS:
            errors.append(f"sttProvider must be one of {VALID_STT_PROVIDERS}")
        if cfg.get("llmProvider") not in VALID_LLM_PROVIDERS:
            errors.append(f"llmProvider must be one of {VALID_LLM_PROVIDERS}")
        if cfg.get("language") not in VALID_LANGUAGES:
            errors.append(f"language must be one of {VALID_LANGUAGES}")
        if cfg.get("outputMode") not in VALID_OUTPUT_MODES:
            errors.append(f"outputMode must be one of {VALID_OUTPUT_MODES}")

        # Hotkeys accept any string the `keyboard` lib can parse.
        # Empty string = mode intentionally disabled (no hotkey) — not an error.
        modes_enabled = cfg.get("modesEnabled") or {}
        for mode_name, key in (cfg.get("hotkeys") or {}).items():
            if (not key or not str(key).strip()) and modes_enabled.get(mode_name, True):
                errors.append(
                    f"hotkeys.{mode_name} is empty but mode is enabled"
                )

        return errors
