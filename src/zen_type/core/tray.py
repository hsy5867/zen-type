"""System tray icon with right-click menu (pywebview-era: callback-based).

Supports live audio-level waveform overlay during RECORDING state — set_level()
is called from the audio thread, we throttle icon updates to ~12 Hz and keep a
short rolling history so the mic shows green sound-wave bars bouncing up/down.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from zen_type.core.constants import PipelineState
from zen_type.core.tray_icons import create_tray_icon

logger = logging.getLogger(__name__)


_LEVEL_HISTORY_LEN = 5
# Windows aggressively rate-limits Shell_NotifyIcon(NIM_MODIFY); > ~5 Hz gets
# silently dropped. Keep slow here — the desktop overlay handles the smooth
# 20 Hz waveform.
_ICON_UPDATE_INTERVAL = 0.25  # seconds (~4 Hz)


class TrayApp:
    """Wraps pystray.Icon, runs in a daemon thread."""

    def __init__(
        self,
        on_open_settings: Callable[[], None] | None = None,
        on_reload: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
        on_open_config_path: Callable[[], None] | None = None,
    ) -> None:
        self.on_open_settings = on_open_settings
        self.on_reload = on_reload
        self.on_quit = on_quit
        self.on_open_config_path = on_open_config_path
        self._icon = None
        self._thread: threading.Thread | None = None
        self._state = PipelineState.IDLE
        self._levels: list[float] = [0.0] * _LEVEL_HISTORY_LEN
        self._last_icon_update: float = 0.0
        self._level_lock = threading.Lock()

    def start(self) -> None:
        import pystray

        def _open_settings(icon, item):  # noqa: ARG001
            if self.on_open_settings:
                self.on_open_settings()

        def _reload(icon, item):  # noqa: ARG001
            if self.on_reload:
                self.on_reload()

        def _config_path(icon, item):  # noqa: ARG001
            if self.on_open_config_path:
                self.on_open_config_path()

        def _quit(icon, item):  # noqa: ARG001
            if self.on_quit:
                self.on_quit()
            icon.stop()

        menu = pystray.Menu(
            pystray.MenuItem("開啟設定", _open_settings, default=True),
            pystray.MenuItem("設定檔位置", _config_path),
            pystray.MenuItem("重新載入設定", _reload),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("結束", _quit),
        )

        self._icon = pystray.Icon(
            "zen-type",
            create_tray_icon(self._state),
            "zen-type",
            menu,
        )

        self._thread = threading.Thread(
            target=self._icon.run, name="zen-type-tray", daemon=True
        )
        self._thread.start()
        logger.info("tray started")

    def _apply_icon(self, img, force_reregister: bool = False) -> None:
        """Push a new icon to pystray, optionally forcing a NIM_DELETE+NIM_ADD cycle.

        pystray 0.19.x on Windows 11 often refuses to redraw in place (Shell
        caches the first icon). ``force_reregister=True`` triggers a hide/show
        cycle that re-registers the icon with the Shell, which reliably breaks
        the cache. We do this on every STATE change but NOT on every level
        update — otherwise the icon would flicker during recording.
        """
        self._icon.icon = img
        try:
            if hasattr(self._icon, "_update_icon") and getattr(self._icon, "visible", False):
                self._icon._update_icon()
            if force_reregister and hasattr(self._icon, "_hide") and hasattr(self._icon, "_show"):
                self._icon._hide()
                self._icon._show()
        except Exception as exc:  # noqa: BLE001
            logger.debug("_apply_icon refresh failed: %s", exc)

    def set_state(self, state: PipelineState) -> None:
        prev = self._state
        self._state = state
        logger.info("tray state %s → %s", prev.value, state.value)
        if prev == PipelineState.RECORDING and state != PipelineState.RECORDING:
            with self._level_lock:
                self._levels = [0.0] * _LEVEL_HISTORY_LEN
        if self._icon is None:
            return
        try:
            with self._level_lock:
                snap = list(self._levels)
            # No force_reregister: previously caused the tray icon to jump to
            # a new taskbar position on every state change. The desktop overlay
            # is now the primary visual feedback, so a stable tray icon is fine.
            self._apply_icon(create_tray_icon(state, levels=snap))
        except Exception as exc:  # noqa: BLE001
            logger.warning("tray set_state failed: %s", exc)

    def set_level(self, level: float) -> None:
        """No-op: the desktop overlay handles live waveform rendering now.
        Rapid tray updates were being rate-limited by Windows and caused the
        icon to jump position in the taskbar on every repaint.
        """
        # Keep the level history for eventual state-change snapshot only.
        with self._level_lock:
            self._levels = self._levels[1:] + [float(level)]

    def notify(self, title: str, message: str) -> None:
        if self._icon is None:
            return
        try:
            self._icon.notify(message, title)
        except Exception as exc:  # noqa: BLE001
            logger.debug("tray notify failed: %s", exc)

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:  # noqa: BLE001
                pass
            self._icon = None
