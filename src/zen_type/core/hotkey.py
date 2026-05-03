"""Multi-mode global hotkey manager supporting combos (e.g. 'left alt+space').

Each Mode (DICTATE/TRANSFORM/ASK) binds to one Push-to-Talk combo:
  • On combo fully pressed → on_press fires (once) and the combo is suppressed
    from reaching other apps.
  • On ANY key of the combo being released → on_release fires.

Combo string format (same as the ``keyboard`` library):
    "left alt+space"    — LeftAlt held + Space
    "left ctrl+space"
    "f9"                — single key
    "caps lock"         — single key with space in its name
    "ctrl+shift+a"      — multiple modifiers
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from zen_type.core.constants import Mode

logger = logging.getLogger(__name__)


# Back-compat mapping: older configs used these Pascal names.
_LEGACY_MAP = {
    "RightAlt": "right alt",
    "RightCtrl": "right ctrl",
    "LeftAlt": "left alt",
    "LeftCtrl": "left ctrl",
    "F9": "f9",
    "F10": "f10",
    "CapsLock": "caps lock",
    "ScrollLock": "scroll lock",
    "Pause": "pause",
}


def normalize_combo(combo: str) -> str:
    """Normalise a user-supplied hotkey string to lowercase parts the keyboard lib accepts."""
    if not combo:
        return ""
    combo = combo.strip()
    # Whole-string legacy map
    if combo in _LEGACY_MAP:
        return _LEGACY_MAP[combo]
    parts = [p.strip() for p in combo.replace(" + ", "+").split("+") if p.strip()]
    out = []
    for p in parts:
        out.append(_LEGACY_MAP.get(p, p.lower()))
    return "+".join(out)


class HotkeyError(Exception):
    """Raised on hotkey registration errors."""


class HotkeyManager:
    """Register/unregister multiple push-to-talk hotkey combos."""

    def __init__(self) -> None:
        # per-mode state
        self._press_handles: dict[Mode, object] = {}
        self._release_handles: dict[Mode, list] = {}
        self._combo_keys: dict[Mode, list[str]] = {}
        self._combo_strings: dict[Mode, str] = {}
        self._active: dict[Mode, bool] = {}
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- public --
    def register(
        self,
        mode: Mode,
        combo: str,
        on_press: Callable[[Mode], None],
        on_release: Callable[[Mode], None],
    ) -> None:
        """Register a single mode's hotkey combo. Replaces any previous binding."""
        import keyboard

        combo_norm = normalize_combo(combo)
        if not combo_norm:
            raise HotkeyError("empty hotkey string")

        parts = combo_norm.split("+")

        with self._lock:
            self._unregister_locked(mode)
            self._active[mode] = False

            # CRITICAL: everything inside the keyboard-library hook thread must
            # return fast (Windows low-level hooks have a hard timeout; slow
            # callbacks cause Windows to silently unhook us, after which ALL
            # zen-type hotkeys stop working). We therefore dispatch the
            # user-supplied on_press/on_release to a fresh daemon thread and
            # return immediately from the hook thread.

            def _fire(fn, m):
                threading.Thread(
                    target=fn,
                    args=(m,),
                    name=f"zen-type-hk-{m.value}",
                    daemon=True,
                ).start()

            def _press_cb(m=mode, fn=on_press, rfn=on_release) -> None:
                with self._lock:
                    was_active = self._active.get(m, False)
                    self._active[m] = True
                if was_active:
                    # Previous release was lost (likely a fast re-press or a
                    # Windows hook timeout). Fire a synthetic release to reset
                    # pipeline state, then trigger the fresh press.
                    logger.warning(
                        "hotkey %s was stuck active — forcing release before retrigger",
                        m.value,
                    )
                    _fire(rfn, m)
                logger.info("hotkey press: %s", m.value)
                _fire(fn, m)

            try:
                press_handle = keyboard.add_hotkey(
                    combo_norm,
                    _press_cb,
                    suppress=True,
                    trigger_on_release=False,
                )
            except Exception as exc:  # noqa: BLE001
                raise HotkeyError(f"failed to bind {combo_norm!r}: {exc}") from exc

            # ----- Release: any key in the combo releasing ends recording -----
            def _release_cb(_event, m=mode, fn=on_release) -> None:  # noqa: ARG001
                with self._lock:
                    if not self._active.get(m):
                        return
                    self._active[m] = False
                _fire(fn, m)

            release_handles = []
            for key in parts:
                try:
                    h = keyboard.on_release_key(key, _release_cb, suppress=False)
                    release_handles.append(h)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("could not hook release for %r: %s", key, exc)

            self._press_handles[mode] = press_handle
            self._release_handles[mode] = release_handles
            self._combo_keys[mode] = parts
            self._combo_strings[mode] = combo_norm
            logger.info("hotkey registered: %s → %s", mode.value, combo_norm)

    def unregister(self, mode: Mode) -> None:
        with self._lock:
            self._unregister_locked(mode)

    def _unregister_locked(self, mode: Mode) -> None:
        import keyboard

        h = self._press_handles.pop(mode, None)
        if h is not None:
            try:
                keyboard.remove_hotkey(h)
            except Exception as exc:  # noqa: BLE001
                logger.debug("remove_hotkey failed for %s: %s", mode, exc)

        for rh in self._release_handles.pop(mode, []):
            try:
                keyboard.unhook(rh)
            except Exception as exc:  # noqa: BLE001
                logger.debug("unhook release failed for %s: %s", mode, exc)

        self._combo_keys.pop(mode, None)
        self._combo_strings.pop(mode, None)
        self._active.pop(mode, None)

    def unhook_all(self) -> None:
        with self._lock:
            for mode in list(self._press_handles.keys()):
                self._unregister_locked(mode)

    def current_combo(self, mode: Mode) -> str | None:
        return self._combo_strings.get(mode)
