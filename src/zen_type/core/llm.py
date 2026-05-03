"""Multi-provider LLM wrapper with three methods: polish / transform / ask."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from zen_type.core.constants import DEFAULT_LLM_MODELS, GROQ_BASE_URL

if TYPE_CHECKING:
    from zen_type.config.settings import Settings

logger = logging.getLogger(__name__)

DEFAULT_TEMPERATURE = 0.3


class LLMError(Exception):
    """Raised when LLM call fails."""


_LANGUAGE_RULES = {
    "zh-TW": (
        "【輸出語言硬性規定】必須使用繁體中文（台灣）輸出。"
        "任何簡體字一律轉換為對應繁體字。"
        "用字遣詞採台灣慣用語（例如「品質」不寫成「质量」、「軟體」不寫成「软件」）。"
    ),
    "zh-CN": (
        "【输出语言硬性规定】必须使用简体中文输出。"
        "任何繁体字一律转换为对应简体字。"
    ),
    "en": "Output must be in English only.",
    "ja": "出力は日本語のみで行ってください。",
}


def _append_language_rule(system: str, language: str) -> str:
    rule = _LANGUAGE_RULES.get(language)
    if not rule:
        return system
    return f"{system}\n\n{rule}"


class LLMProcessor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # ---- Public API ----
    def polish(self, raw_text: str, context_hint: str | None = None) -> str:
        """Clean up speech-to-text output: remove fillers, add punctuation, keep meaning."""
        text = (raw_text or "").strip()
        if len(text) < 2:
            return text

        cfg = self.settings.load()
        system = cfg.get("polishPrompt", "")
        system = _append_language_rule(system, cfg.get("language", "auto"))
        if context_hint:
            system = f"{system}\n\n[情境] {context_hint}"

        try:
            return self._chat(cfg, system, text, temperature=0.2)
        except LLMError as exc:
            logger.warning("polish failed (%s) — returning raw text", exc)
            return text

    def transform(self, original_text: str, instruction: str) -> str:
        """Rewrite original_text according to the spoken instruction."""
        original_text = (original_text or "").strip()
        instruction = (instruction or "").strip()
        if not original_text or not instruction:
            return original_text

        cfg = self.settings.load()
        system = cfg.get("transformPrompt", "")
        system = _append_language_rule(system, cfg.get("language", "auto"))
        user = f"【改寫指令】{instruction}\n\n【原始文字】\n{original_text}"

        try:
            return self._chat(cfg, system, user, temperature=0.4)
        except LLMError as exc:
            logger.warning("transform failed (%s) — returning original", exc)
            return original_text

    def ask(self, question: str, context_hint: str | None = None) -> str:
        """Answer a spoken question."""
        question = (question or "").strip()
        if not question:
            return ""

        cfg = self.settings.load()
        system = cfg.get("askPrompt", "")
        system = _append_language_rule(system, cfg.get("language", "auto"))
        if context_hint:
            system = f"{system}\n\n[情境] {context_hint}"

        try:
            return self._chat(cfg, system, question, temperature=0.5)
        except LLMError as exc:
            logger.warning("ask failed (%s) — returning question back", exc)
            return question

    # ---- Dispatch ----
    def _chat(
        self,
        cfg: dict,
        system: str,
        user: str,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> str:
        provider = cfg.get("llmProvider", "groq")
        model = cfg.get("llmModel") or DEFAULT_LLM_MODELS.get(provider, "")

        if provider == "groq":
            return self._openai_compat(
                cfg, system, user, model, temperature, base_url=GROQ_BASE_URL, key_name="groq"
            )
        if provider == "openai":
            return self._openai_compat(
                cfg, system, user, model, temperature, base_url=None, key_name="openai"
            )
        if provider == "anthropic":
            return self._anthropic(cfg, system, user, model, temperature)
        if provider == "ollama":
            return self._ollama(cfg, system, user, model, temperature)
        raise LLMError(f"unknown llmProvider: {provider}")

    # ---- Groq / OpenAI (identical SDK) ----
    def _openai_compat(
        self,
        cfg: dict,
        system: str,
        user: str,
        model: str,
        temperature: float,
        base_url: str | None,
        key_name: str,
    ) -> str:
        from openai import OpenAI

        api_key = (cfg.get("apiKeys") or {}).get(key_name)
        if not api_key:
            raise LLMError(f"{key_name} API key is not configured")

        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"{key_name} chat failed: {exc}") from exc

        content = resp.choices[0].message.content or ""
        return content.strip()

    # ---- Anthropic ----
    def _anthropic(
        self, cfg: dict, system: str, user: str, model: str, temperature: float
    ) -> str:
        import anthropic

        api_key = (cfg.get("apiKeys") or {}).get("anthropic")
        if not api_key:
            raise LLMError("Anthropic API key is not configured")

        client = anthropic.Anthropic(api_key=api_key)
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=4096,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Anthropic chat failed: {exc}") from exc

        # Concat all text blocks
        parts = [blk.text for blk in resp.content if getattr(blk, "type", "") == "text"]
        return "".join(parts).strip()

    # ---- Ollama (local) ----
    def _ollama(
        self, cfg: dict, system: str, user: str, model: str, temperature: float
    ) -> str:
        import requests

        endpoint = ((cfg.get("apiKeys") or {}).get("ollama") or "http://localhost:11434").rstrip("/")
        url = f"{endpoint}/api/chat"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": temperature},
            "stream": False,
        }

        try:
            r = requests.post(url, json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Ollama chat failed: {exc}") from exc

        return (data.get("message", {}).get("content") or "").strip()
