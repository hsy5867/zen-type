"""Text injection via clipboard, optionally followed by Ctrl+V auto-paste.

Critical detail for Alt+Space-style Push-to-Talk hotkeys:

    When the user releases Alt+Space and we *immediately* send Ctrl+V via
    pyautogui, the Alt key may still be physically in its up-transition (or
    Windows may still consider it "down" for a few more ms). The result is
    the OS seeing ``Alt+Ctrl+V`` which most apps interpret as a NO-OP or a
    different shortcut entirely — the paste silently fails and sometimes the
    keyboard gets stuck.

    Fix (from the referenced reference implementation video): forcibly release
    every modifier/space key before and after the Ctrl+V, with a short settle
    delay on each side.
"""

from __future__ import annotations

import logging
import time

from zen_type.core.constants import CLIPBOARD_SETTLE_SECONDS

logger = logging.getLogger(__name__)

# Keys we forcibly release before and after pasting. ``keyboard.release()``
# is a no-op if the key is not actually held, so sending all of these is safe.
_MODIFIERS_TO_RELEASE = (
    "alt", "left alt", "right alt",
    "ctrl", "left ctrl", "right ctrl",
    "shift", "left shift", "right shift",
    "left windows", "right windows",
    "space",
)

# Extra delay (on top of CLIPBOARD_SETTLE_SECONDS) to let the key-up events
# from the hotkey propagate through the OS before we send Ctrl+V.
_MODIFIER_RELEASE_SLEEP = 0.05


def _force_release_modifiers() -> None:
    """Release every key that could accidentally compose with Ctrl+V."""
    try:
        import keyboard
    except Exception:  # noqa: BLE001
        return
    for key in _MODIFIERS_TO_RELEASE:
        try:
            keyboard.release(key)
        except Exception:  # noqa: BLE001
            # Some scan codes aren't mapped on all layouts — safe to ignore.
            pass


class TextInjector:
    """Injects text to the active window.

    Modes:
        "clipboard"  — copy only (user pastes manually)
        "auto_paste" — copy + simulate Ctrl+V
    """

    def __init__(self, mode: str = "auto_paste", restore_clipboard: bool = True) -> None:
        self.mode = mode
        self.restore_clipboard = restore_clipboard

    def inject(self, text: str) -> None:
        if not text:
            return

        import pyperclip

        previous: str | None = None
        if self.restore_clipboard:
            try:
                previous = pyperclip.paste()
            except Exception as exc:  # noqa: BLE001
                logger.debug("cannot read previous clipboard: %s", exc)
                previous = None

        try:
            pyperclip.copy(text)
        except Exception as exc:  # noqa: BLE001
            logger.error("clipboard copy failed: %s", exc)
            return

        # 1) Wait for the hotkey's own key-up events to finish propagating.
        time.sleep(CLIPBOARD_SETTLE_SECONDS + _MODIFIER_RELEASE_SLEEP)

        if self.mode == "auto_paste":
            # 2) Forcibly clear any stuck Alt/Ctrl/Shift/Space/Win.
            _force_release_modifiers()
            time.sleep(_MODIFIER_RELEASE_SLEEP)

            # 3) Send the paste.
            try:
                import pyautogui

                pyautogui.hotkey("ctrl", "v")
            except Exception as exc:  # noqa: BLE001
                logger.error("auto-paste failed: %s", exc)

            # 4) Release again in case Ctrl+V left anything stuck.
            time.sleep(_MODIFIER_RELEASE_SLEEP)
            _force_release_modifiers()

        if self.restore_clipboard and previous is not None:
            # Give the paste a moment before we overwrite the clipboard again.
            time.sleep(CLIPBOARD_SETTLE_SECONDS * 3)
            try:
                pyperclip.copy(previous)
            except Exception as exc:  # noqa: BLE001
                logger.debug("cannot restore clipboard: %s", exc)

    def capture_selection(self) -> str:
        """Copy current selection (Ctrl+C) and read from clipboard.

        Used by Transform mode — grabs whatever the user had highlighted so the LLM
        can rewrite it according to their spoken instruction.
        """
        import pyautogui
        import pyperclip

        # Preserve existing clipboard so we can restore it later
        try:
            before = pyperclip.paste()
        except Exception:  # noqa: BLE001
            before = ""

        try:
            pyautogui.hotkey("ctrl", "c")
        except Exception as exc:  # noqa: BLE001
            logger.error("Ctrl+C failed: %s", exc)
            return ""

        time.sleep(CLIPBOARD_SETTLE_SECONDS * 2)

        try:
            selection = pyperclip.paste()
        except Exception as exc:  # noqa: BLE001
            logger.error("clipboard read failed: %s", exc)
            selection = ""

        # If clipboard didn't change, nothing was selected
        if selection == before:
            return ""
        return selection or ""
