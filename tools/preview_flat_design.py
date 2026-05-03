"""Render the new flat-design overlay + tray icons for all 6 pipeline states.

Output:
  refer_Report/2026-0501_<HHmm>_flat-design-preview/PROD8_full_preview.png

The script imports the production renderers verbatim (no re-implementation), so
what you see here is exactly what the running app will draw.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# Make src/ importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from zen_type.core.constants import PipelineState  # noqa: E402
from zen_type.core.overlay import (  # noqa: E402
    _CHROMA_RGB,
    _compute_layout,
    _render_pill,
)
from zen_type.core.tray_icons import create_tray_icon  # noqa: E402

STATES = [
    PipelineState.IDLE,
    PipelineState.RECORDING,
    PipelineState.TRANSCRIBING,
    PipelineState.POLISHING,
    PipelineState.INJECTING,
    PipelineState.ERROR,
]
NAMES = ["IDLE 待機", "RECORDING 錄音中", "TRANSCRIBING 辨識中",
         "POLISHING 潤稿中", "INJECTING 貼上中", "ERROR 錯誤"]


def _load_caption_font(size: int):
    candidates = [
        r"C:\Windows\Fonts\msjh.ttc",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _chroma_to_alpha(rgb_img: Image.Image) -> Image.Image:
    """The pill is returned as RGB with chroma magenta as transparent. Convert
    to RGBA so it can sit on a non-magenta backdrop."""
    rgba = rgb_img.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    for y in range(h):
        for x in range(w):
            if px[x, y][:3] == _CHROMA_RGB:
                px[x, y] = (0, 0, 0, 0)
    return rgba


def render_all() -> Image.Image:
    layout = _compute_layout()
    pill_w = layout["W"]
    pill_h = layout["H"]

    # Wave levels for RECORDING (cosmetic, mid-amplitude)
    levels = [0.3, 0.6, 0.9, 0.7, 0.5, 0.8, 0.4]

    # Layout: 3 columns × 2 rows of (pill | label | tray-16 | tray-32 | tray-64)
    cell_pad_x = 24
    cell_pad_y = 18
    label_h = 26
    tray_block_w = 16 + 8 + 32 + 8 + 64
    cell_w = pill_w + 24 + tray_block_w + cell_pad_x * 2
    cell_h = pill_h + label_h + cell_pad_y * 2

    cols = 2
    rows = 3
    title_h = 60
    bg_color = (250, 250, 250)
    canvas = Image.new("RGB",
                       (cell_w * cols, title_h + cell_h * rows),
                       bg_color)
    cd = ImageDraw.Draw(canvas)

    title_font = _load_caption_font(22)
    label_font = _load_caption_font(16)
    cd.text((20, 16),
            "zen-type — flat-design preview (overlay pill + tray @ 16/32/64px)",
            fill=(40, 40, 40), font=title_font)

    for idx, (state, name) in enumerate(zip(STATES, NAMES)):
        col = idx % cols
        row = idx // cols
        ox = col * cell_w
        oy = title_h + row * cell_h

        # Cell background — subtle separator
        cd.rectangle((ox, oy, ox + cell_w - 1, oy + cell_h - 1),
                     outline=(220, 220, 220), width=1)

        # Pill (already comes back as RGB w/ chroma key; convert)
        pill_rgb = _render_pill(state, levels, layout)
        pill_rgba = _chroma_to_alpha(pill_rgb)
        canvas.paste(pill_rgba,
                     (ox + cell_pad_x, oy + cell_pad_y + label_h),
                     pill_rgba)

        # Tray icons at 16, 32, 64
        tray_x = ox + cell_pad_x + pill_w + 24
        tray_y_base = oy + cell_pad_y + label_h + (pill_h - 64) // 2
        for i, sz in enumerate((16, 32, 64)):
            ic = create_tray_icon(state, size=sz)
            offsets = (0, 16 + 8, 16 + 8 + 32 + 8)
            tx = tray_x + offsets[i]
            ty = tray_y_base + (64 - sz)
            canvas.paste(ic, (tx, ty), ic)

        # Label above
        cd.text((ox + cell_pad_x, oy + cell_pad_y),
                name, fill=(60, 60, 60), font=label_font)
        cd.text((tray_x, oy + cell_pad_y),
                "tray  16   32       64", fill=(120, 120, 120),
                font=_load_caption_font(12))

    return canvas


def render_zoom_row() -> Image.Image:
    """A separate 'zoom' image: each state's tray icon at 256px so the mic
    geometry is unambiguous. Helpful when small differences between revisions
    need to be visible."""
    big = 256
    pad = 12
    label_h = 28
    cell_w = big + pad * 2
    cell_h = big + label_h + pad * 2
    canvas = Image.new("RGB", (cell_w * len(STATES), cell_h + 30), (250, 250, 250))
    cd = ImageDraw.Draw(canvas)
    title_font = _load_caption_font(18)
    label_font = _load_caption_font(14)
    cd.text((20, 6), "256px zoom (one icon per state — geometry check)",
            fill=(40, 40, 40), font=title_font)
    for idx, (state, name) in enumerate(zip(STATES, NAMES)):
        ic = create_tray_icon(state, size=big)
        ox = idx * cell_w
        oy = 30
        canvas.paste(ic, (ox + pad, oy + label_h + pad), ic)
        cd.text((ox + pad, oy + 4), name, fill=(60, 60, 60), font=label_font)
        cd.rectangle((ox, oy, ox + cell_w - 1, oy + cell_h - 1),
                     outline=(220, 220, 220), width=1)
    return canvas


def main() -> int:
    out_dir = ROOT / "refer_Report" / (
        datetime.now().strftime("2026-0502_%H%M") + "_flat-design-preview"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    img = render_all()
    out_path = out_dir / "PROD_full_preview.png"
    img.save(out_path)
    print(f"wrote {out_path}")
    print(f"size: {img.size}")

    zoom = render_zoom_row()
    zoom_path = out_dir / "PROD_zoom_256.png"
    zoom.save(zoom_path)
    print(f"wrote {zoom_path}")
    print(f"size: {zoom.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
