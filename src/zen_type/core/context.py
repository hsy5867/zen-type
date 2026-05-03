"""Detect the foreground window to pick a context template.

Heuristic-only: pywin32 is optional. When unavailable, returns "default".
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

# Simple keyword → template mapping
APP_HINTS = {
    "email": ("outlook", "gmail", "mail", "thunderbird"),
    "chat": ("slack", "discord", "line", "teams", "telegram", "messenger", "whatsapp"),
    "code": ("visual studio code", "vscode", "pycharm", "intellij", "sublime", "neovim", "vim"),
    "doc": ("word", "google docs", "notion", "obsidian", "onenote", "pages"),
}


def get_active_window_title() -> str:
    """Return the foreground window title (empty string on failure or non-Windows)."""
    if sys.platform != "win32":
        return ""
    try:
        import win32gui  # type: ignore

        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd) or ""
    except Exception as exc:  # noqa: BLE001
        logger.debug("get_active_window_title failed: %s", exc)
        return ""


def detect_context_key(title: str | None = None) -> str:
    """Return a context template key: 'email' / 'chat' / 'code' / 'doc' / 'default'."""
    title = (title if title is not None else get_active_window_title()).lower()
    if not title:
        return "default"
    for key, hints in APP_HINTS.items():
        if any(h in title for h in hints):
            return key
    return "default"
