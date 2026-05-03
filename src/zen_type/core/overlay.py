"""Desktop floating overlay — variant E (reference-image style).

Pill card with a coloured disc + white mic on the left, dot indicator (or live
waveform during RECORDING) in the middle, and a big bold CJK status label on
the right. Each pipeline state has its own disc colour and pill border tint so
the user can identify the state at a glance without reading the text.

The pill is rendered with Pillow each frame and shown via ``PIL.ImageTk``
``PhotoImage`` on a ``tk.Canvas``. To keep Windows ``-transparentcolor`` chroma
keying working with rounded pill edges, the alpha channel is thresholded to
binary against a magenta background — this gives hard-edge corners but avoids
purple fringing.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Callable

from zen_type.core.constants import PipelineState

logger = logging.getLogger(__name__)


# ===== Visual config — flat design, per-state palette =======================
# Pill body is near-white with the faintest state tint; the saturated colour
# lives ONLY on the left disc, the 1px border and the dot/wave indicator.
# No shadows, no gradients, no glow — pure flat fills.

_DISC_COLOR = {
    PipelineState.IDLE:         (208, 208, 208),  # #D0D0D0 light gray
    PipelineState.RECORDING:    (220,  53,  69),  # #DC3545
    PipelineState.TRANSCRIBING: (255, 152,   0),  # #FF9800
    PipelineState.POLISHING:    ( 33, 150, 243),  # #2196F3
    PipelineState.INJECTING:    ( 76, 175,  80),  # #4CAF50
    PipelineState.ERROR:        (138, 138, 138),  # #8A8A8A
}

# 1px solid border, fully opaque, saturated state colour
_BORDER_COLOR = {
    PipelineState.IDLE:         (204, 204, 204, 255),  # #CCCCCC
    PipelineState.RECORDING:    (245, 198, 203, 255),  # #F5C6CB
    PipelineState.TRANSCRIBING: (255, 224, 178, 255),  # #FFE0B2
    PipelineState.POLISHING:    (179, 217, 255, 255),  # #B3D9FF
    PipelineState.INJECTING:    (200, 230, 201, 255),  # #C8E6C9
    PipelineState.ERROR:        (204, 204, 204, 255),  # #CCCCCC
}

# Pill body: near-white with very faint state tint
_CARD_FILL_BY_STATE = {
    PipelineState.IDLE:         (245, 245, 245),  # #F5F5F5
    PipelineState.RECORDING:    (255, 245, 245),  # #FFF5F5
    PipelineState.TRANSCRIBING: (255, 248, 240),  # #FFF8F0
    PipelineState.POLISHING:    (240, 248, 255),  # #F0F8FF
    PipelineState.INJECTING:    (240, 255, 244),  # #F0FFF4
    PipelineState.ERROR:        (245, 245, 245),  # #F5F5F5
}

# Dot indicator / waveform colour: same saturated state colour as disc
_DOT_COLOR = {
    PipelineState.IDLE:         (153, 153, 153),  # #999999 (light enough not to dominate)
    PipelineState.TRANSCRIBING: (255, 152,   0),
    PipelineState.POLISHING:    ( 33, 150, 243),
    PipelineState.INJECTING:    ( 76, 175,  80),
    PipelineState.ERROR:        (160, 160, 160),
}

# Mic colour per state — white on every saturated disc, dark gray on the
# light-gray IDLE disc (where white would have no contrast).
_MIC_COLOR_BY_STATE = {
    PipelineState.IDLE:         ( 85,  85,  85),  # #555555
    PipelineState.RECORDING:    (255, 255, 255),
    PipelineState.TRANSCRIBING: (255, 255, 255),
    PipelineState.POLISHING:    (255, 255, 255),
    PipelineState.INJECTING:    (255, 255, 255),
    PipelineState.ERROR:        (255, 255, 255),
}

_LABEL = {
    PipelineState.IDLE:         "待機",
    PipelineState.RECORDING:    "錄音中",
    PipelineState.TRANSCRIBING: "辨識中",
    PipelineState.POLISHING:    "潤稿中",
    PipelineState.INJECTING:    "貼上中",
    PipelineState.ERROR:        "錯誤",
}

_LABEL_COLOR = (51, 51, 51)         # #333333
_WAVE_REC_COLOR = (220, 53, 69)     # matches RECORDING disc

_WAVE_BARS = 7
_CHROMA_HEX = "#ff00fe"
_CHROMA_RGB = (255, 0, 254)


# ===== Helpers ===============================================================

def _load_font(size: int, bold: bool = True):
    """Microsoft JhengHei first (carries CJK + Latin glyphs), then fall backs."""
    from PIL import ImageFont
    candidates = [
        r"C:\Windows\Fonts\msjhbd.ttc" if bold else r"C:\Windows\Fonts\msjh.ttc",
        r"C:\Windows\Fonts\msjh.ttc",
        r"C:\Windows\Fonts\seguisb.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# NOTE: the hand-drawn 4-shape mic was replaced with the bundled reference
# image in zen_type/assets/mic_reference.png. See `mic_glyph.paste_mic`.


def _draw_dots(draw, cx: int, cy: int, n: int, dot_r: int, gap: int,
               color: tuple[int, int, int]) -> None:
    total_w = n * (dot_r * 2) + (n - 1) * gap
    start_x = cx - total_w // 2
    for i in range(n):
        x = start_x + i * (dot_r * 2 + gap)
        draw.ellipse((x, cy - dot_r, x + dot_r * 2, cy + dot_r), fill=color)


def _draw_wave(draw, cx: int, cy: int, n: int, bar_w: int, gap: int,
               max_h: int, levels: list[float],
               color: tuple[int, int, int]) -> None:
    total_w = n * bar_w + (n - 1) * gap
    start_x = cx - total_w // 2
    for i in range(n):
        lvl = levels[i] if i < len(levels) else 0.1
        h = max(2, int(max_h * max(0.08, min(1.0, float(lvl)))))
        x1 = start_x + i * (bar_w + gap)
        draw.rounded_rectangle(
            (x1, cy - h, x1 + bar_w, cy + h), radius=2, fill=color,
        )


def _compute_layout() -> dict:
    """Pre-compute pill width once based on the longest CJK label."""
    from PIL import Image, ImageDraw
    H = 64
    f = _load_font(32, bold=True)
    LEFT_PAD = 6
    GAP_DISC_MID = 14
    MID_W = 50
    GAP_MID_TEXT = 14
    RIGHT_PAD = 18
    disc_r = (H - 10) // 2

    tmp = Image.new("RGBA", (1, 1))
    td = ImageDraw.Draw(tmp)
    max_tw = 0
    max_th = 0
    for label in _LABEL.values():
        bbox = td.textbbox((0, 0), label, font=f)
        max_tw = max(max_tw, bbox[2] - bbox[0])
        max_th = max(max_th, bbox[3] - bbox[1])
    W = LEFT_PAD + 2 * disc_r + GAP_DISC_MID + MID_W + GAP_MID_TEXT + max_tw + RIGHT_PAD
    return {
        "W": W, "H": H, "font": f,
        "LEFT_PAD": LEFT_PAD, "RIGHT_PAD": RIGHT_PAD,
        "GAP_DISC_MID": GAP_DISC_MID, "MID_W": MID_W,
        "GAP_MID_TEXT": GAP_MID_TEXT,
        "disc_r": disc_r, "max_tw": max_tw, "max_th": max_th,
    }


def _render_pill(state: PipelineState, levels: list[float], layout: dict):
    """Render the pill as RGBA, then composite onto chroma magenta with a
    binary alpha mask so Tk's ``-transparentcolor`` keys out the surroundings."""
    from PIL import Image, ImageDraw

    W = layout["W"]
    H = layout["H"]
    f = layout["font"]
    disc_r = layout["disc_r"]

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Pill card — near-white body with very faint state tint, 1px border
    border = _BORDER_COLOR.get(state, _BORDER_COLOR[PipelineState.IDLE])
    card_fill = _CARD_FILL_BY_STATE.get(state, _CARD_FILL_BY_STATE[PipelineState.IDLE])
    d.rounded_rectangle(
        (0, 0, W - 1, H - 1), radius=H // 2,
        fill=card_fill + (255,), outline=border, width=1,
    )

    # Coloured disc on the left — no ring, no shadow
    cx_mic = layout["LEFT_PAD"] + disc_r
    cy_mic = H // 2
    disc_color = _DISC_COLOR.get(state, _DISC_COLOR[PipelineState.IDLE])
    d.ellipse(
        (cx_mic - disc_r, cy_mic - disc_r, cx_mic + disc_r, cy_mic + disc_r),
        fill=disc_color,
    )
    mic_color = _MIC_COLOR_BY_STATE.get(state, (255, 255, 255))
    # Mic glyph from bundled reference PNG — height ≈ 70% of disc diameter.
    from zen_type.core.mic_glyph import paste_mic
    paste_mic(img, cx_mic, cy_mic, int(disc_r * 2 * 0.70), mic_color)

    # Middle: dots when idle/processing, waveform during RECORDING
    mid_cx = cx_mic + disc_r + layout["GAP_DISC_MID"] + layout["MID_W"] // 2
    mid_cy = H // 2
    if state == PipelineState.RECORDING:
        _draw_wave(d, mid_cx, mid_cy, n=_WAVE_BARS, bar_w=4, gap=3,
                   max_h=14, levels=levels, color=_WAVE_REC_COLOR)
    else:
        _draw_dots(d, mid_cx, mid_cy, n=5, dot_r=3, gap=6,
                   color=_DOT_COLOR.get(state, _DOT_COLOR[PipelineState.IDLE]))

    # Big bold status text on right
    text_x = cx_mic + disc_r + layout["GAP_DISC_MID"] + layout["MID_W"] + layout["GAP_MID_TEXT"]
    label = _LABEL[state]
    bbox = d.textbbox((0, 0), label, font=f)
    th = bbox[3] - bbox[1]
    text_y = (H - th) // 2 - bbox[1]
    d.text((text_x, text_y), label, font=f, fill=_LABEL_COLOR)

    # Composite onto chroma magenta with binary alpha mask
    bg = Image.new("RGB", img.size, _CHROMA_RGB)
    alpha = img.split()[-1]
    mask = alpha.point(lambda v: 255 if v > 128 else 0).convert("L")
    bg.paste(img.convert("RGB"), mask=mask)
    return bg


# ===== Overlay class =========================================================

class Overlay:
    """Floating, draggable, always-on-top status widget."""

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

        self._q: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._state = PipelineState.IDLE
        self._levels: list[float] = [0.0] * _WAVE_BARS
        self._drag_x = 0
        self._drag_y = 0

        self._root = None
        self._canvas = None
        self._photo = None       # keep PhotoImage reference alive
        self._photo_id = None
        self._menu = None
        self._layout: dict | None = None

    # ---------------------------------------------------------------- Public
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_flag.clear()
        self._thread = threading.Thread(
            target=self._run, name="zen-type-overlay", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_flag.set()
        self._q.put(("quit", None))

    def set_state(self, state: PipelineState) -> None:
        self._q.put(("state", state))

    def set_level(self, level: float) -> None:
        self._q.put(("level", float(level)))

    # -------------------------------------------------------------- Thread
    def _run(self) -> None:
        # Declare per-monitor DPI awareness so Windows doesn't bitmap-stretch
        # the overlay on high-DPI displays. Without this, the pill shows up
        # scaled-up on first paint and "shrinks" only after some other GUI
        # module flips the process DPI flag. Calling early & idempotently fixes
        # the initial render.
        import sys
        if sys.platform == "win32":
            try:
                import ctypes
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_V2
                except Exception:
                    ctypes.windll.user32.SetProcessDPIAware()
            except Exception as exc:  # noqa: BLE001
                logger.debug("SetProcessDpiAwareness failed (non-fatal): %s", exc)

        try:
            import tkinter as tk
        except Exception as exc:  # noqa: BLE001
            logger.warning("tkinter unavailable — overlay disabled: %s", exc)
            return

        try:
            self._root = tk.Tk()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tk() failed — overlay disabled: %s", exc)
            return

        try:
            self._layout = _compute_layout()
        except Exception as exc:  # noqa: BLE001
            logger.warning("overlay layout failed — disabled: %s", exc)
            try:
                self._root.destroy()
            except Exception:
                pass
            return

        W = self._layout["W"]
        H = self._layout["H"]

        root = self._root
        root.title("zen-type")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        try:
            root.wm_attributes("-transparentcolor", _CHROMA_HEX)
        except Exception:
            pass

        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        x = screen_w - W - 40
        y = screen_h - H - 80
        root.geometry(f"{W}x{H}+{x}+{y}")

        self._canvas = tk.Canvas(
            root, width=W, height=H,
            bg=_CHROMA_HEX,
            highlightthickness=0,
            borderwidth=0,
        )
        self._canvas.pack(fill="both", expand=True)
        self._photo_id = self._canvas.create_image(0, 0, anchor="nw")
        self._update_image()

        # Drag-to-move (left button)
        def _start_drag(e):
            self._drag_x, self._drag_y = e.x, e.y

        def _do_drag(e):
            nx = root.winfo_x() + e.x - self._drag_x
            ny = root.winfo_y() + e.y - self._drag_y
            root.geometry(f"+{nx}+{ny}")

        self._canvas.bind("<Button-1>", _start_drag)
        self._canvas.bind("<B1-Motion>", _do_drag)

        # Right-click menu
        menu = tk.Menu(root, tearoff=0, font=("Segoe UI", 14))

        def _fire(fn):
            if fn is None:
                return
            threading.Thread(
                target=fn, name="zen-type-overlay-menu", daemon=True
            ).start()

        menu.add_command(label="開啟設定", command=lambda: _fire(self.on_open_settings))
        menu.add_command(label="設定檔位置", command=lambda: _fire(self.on_open_config_path))
        menu.add_command(label="重新載入設定", command=lambda: _fire(self.on_reload))
        menu.add_separator()
        menu.add_command(label="結束", command=lambda: _fire(self.on_quit))

        def _popup(e):
            try:
                menu.tk_popup(e.x_root, e.y_root)
            finally:
                menu.grab_release()

        self._canvas.bind("<Button-3>", _popup)
        self._menu = menu

        self._poll()

        try:
            root.mainloop()
        except Exception as exc:  # noqa: BLE001
            logger.debug("overlay mainloop exited: %s", exc)

    def _poll(self) -> None:
        if self._stop_flag.is_set():
            try:
                self._root.destroy()
            except Exception:
                pass
            return
        dirty = False
        try:
            while True:
                kind, val = self._q.get_nowait()
                if kind == "quit":
                    self._stop_flag.set()
                    break
                elif kind == "state":
                    self._state = val
                    dirty = True
                elif kind == "level":
                    self._levels = self._levels[1:] + [max(0.0, min(1.0, val))]
                    dirty = True
        except queue.Empty:
            pass

        if dirty:
            self._update_image()

        self._root.after(50, self._poll)

    def _update_image(self) -> None:
        from PIL import ImageTk
        try:
            img = _render_pill(self._state, self._levels, self._layout)
        except Exception as exc:  # noqa: BLE001
            logger.exception("overlay render failed: %s", exc)
            return
        self._photo = ImageTk.PhotoImage(img)
        if self._photo_id is not None and self._canvas is not None:
            self._canvas.itemconfigure(self._photo_id, image=self._photo)
