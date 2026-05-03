"""Generate three overlay design mockups + tray-icon mockups for visual review.

Run:
    uv run python tools/design_mockups.py

Outputs land in ``refer_Report/<timestamp>_overlay圖示3款設計mockup比較/`` so the
user can flip between PNGs and pick a direction. The script is intentionally
self-contained — it does NOT touch the live overlay.py / tray_icons.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_DIR = Path(__file__).resolve().parent.parent / "refer_Report" / "2026-0501_1204_overlay圖示3款設計mockup比較"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---- Try to load decent fonts; fall back gracefully ----------------------
# Microsoft JhengHei carries both Latin AND CJK glyphs, so we put it FIRST —
# Segoe UI alone leaves all Chinese characters as tofu boxes.
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\msjhbd.ttc" if bold else r"C:\Windows\Fonts\msjh.ttc",
        r"C:\Windows\Fonts\msjh.ttc",
        r"C:\Windows\Fonts\seguisb.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        if not path:
            continue
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# =============================================================================
# Helpers — common primitives reused across variants
# =============================================================================

def _drop_shadow(img: Image.Image, *, blur: int = 8, offset: tuple[int, int] = (0, 3),
                 color: tuple[int, int, int, int] = (0, 0, 0, 80)) -> Image.Image:
    """Return ``img`` with a soft drop shadow underneath.

    Used to lift the overlay card off the desktop background — the single
    biggest perceptual upgrade vs the current flat chroma-key version.
    """
    shadow = Image.new("RGBA", (img.width + blur * 2, img.height + blur * 2), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    # Use the alpha channel as the shadow mask
    alpha = img.getchannel("A")
    mask = Image.new("RGBA", img.size, color)
    mask.putalpha(alpha)
    shadow.paste(mask, (blur + offset[0], blur + offset[1]), alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    shadow.alpha_composite(img, dest=(blur, blur))
    return shadow


def _rounded_rect(draw: ImageDraw.ImageDraw, xy, radius, fill=None, outline=None, width=0):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _mic_glyph(draw: ImageDraw.ImageDraw, cx: int, cy: int, *, glyph_size: int,
               color: tuple[int, int, int], style: str = "capsule_arch") -> None:
    """Microphone glyph in one of several styles.

    ``glyph_size`` controls the overall mic height in pixels.
    ``style`` is one of ``capsule_arch`` (default — original),
    ``solid_filled``, ``outline``, ``grille``, ``podcast``, ``modern_flat``.
    """
    if style == "capsule_arch":
        return _mic_capsule_arch(draw, cx, cy, glyph_size, color)
    if style == "solid_filled":
        return _mic_solid_filled(draw, cx, cy, glyph_size, color)
    if style == "outline":
        return _mic_outline(draw, cx, cy, glyph_size, color)
    if style == "grille":
        return _mic_grille(draw, cx, cy, glyph_size, color)
    if style == "podcast":
        return _mic_podcast(draw, cx, cy, glyph_size, color)
    if style == "modern_flat":
        return _mic_modern_flat(draw, cx, cy, glyph_size, color)
    raise ValueError(f"unknown mic style: {style!r}")


def _mic_capsule_arch(draw, cx, cy, glyph_size, color):
    """Original: capsule body + open arch base + stem + base line."""
    body_w = int(glyph_size * 0.46)
    body_h = int(glyph_size * 0.62)
    body_x1 = cx - body_w // 2
    body_y1 = cy - body_h // 2 - int(glyph_size * 0.05)
    body_x2 = body_x1 + body_w
    body_y2 = body_y1 + body_h
    draw.rounded_rectangle((body_x1, body_y1, body_x2, body_y2),
                           radius=body_w // 2, fill=color)
    arch_w = int(glyph_size * 0.72)
    arch_h = int(glyph_size * 0.34)
    arch_x1 = cx - arch_w // 2
    arch_x2 = cx + arch_w // 2
    arch_y1 = body_y2 - arch_h // 2
    arch_y2 = arch_y1 + arch_h
    line_w = max(2, glyph_size // 22)
    draw.arc((arch_x1, arch_y1, arch_x2, arch_y2), start=0, end=180,
             fill=color, width=line_w)
    stem_top = arch_y1 + arch_h // 2
    stem_bottom = stem_top + int(glyph_size * 0.18)
    draw.line((cx, stem_top, cx, stem_bottom), fill=color, width=line_w)
    base_w = int(glyph_size * 0.36)
    draw.line((cx - base_w // 2, stem_bottom, cx + base_w // 2, stem_bottom),
              fill=color, width=line_w)


def _mic_solid_filled(draw, cx, cy, glyph_size, color):
    """Bold solid mic — fully filled capsule, no separate arch (Material-ish)."""
    body_w = int(glyph_size * 0.50)
    body_h = int(glyph_size * 0.66)
    body_y1 = cy - body_h // 2 - int(glyph_size * 0.06)
    body_y2 = body_y1 + body_h
    draw.rounded_rectangle((cx - body_w // 2, body_y1,
                            cx + body_w // 2, body_y2),
                           radius=body_w // 2, fill=color)
    # Curved cradle below the body, rendered as a thick filled arc band
    cradle_w = int(glyph_size * 0.78)
    cradle_h = int(glyph_size * 0.42)
    cradle_x1 = cx - cradle_w // 2
    cradle_y1 = body_y2 - cradle_h // 2
    cradle_x2 = cx + cradle_w // 2
    cradle_y2 = cradle_y1 + cradle_h
    line_w = max(3, glyph_size // 14)
    draw.arc((cradle_x1, cradle_y1, cradle_x2, cradle_y2),
             start=15, end=165, fill=color, width=line_w)
    # Short stand
    stand_top = cradle_y1 + cradle_h // 2 + line_w // 2
    stand_bottom = stand_top + int(glyph_size * 0.12)
    draw.rectangle((cx - line_w // 2, stand_top,
                    cx + line_w // 2, stand_bottom), fill=color)


def _mic_outline(draw, cx, cy, glyph_size, color):
    """Line-art mic — thin outlines only, no fill. Modern, lightweight feel."""
    body_w = int(glyph_size * 0.46)
    body_h = int(glyph_size * 0.62)
    body_x1 = cx - body_w // 2
    body_y1 = cy - body_h // 2 - int(glyph_size * 0.05)
    body_x2 = body_x1 + body_w
    body_y2 = body_y1 + body_h
    line_w = max(2, glyph_size // 18)
    draw.rounded_rectangle((body_x1, body_y1, body_x2, body_y2),
                           radius=body_w // 2,
                           outline=color, width=line_w)
    # Cradle arc
    cradle_w = int(glyph_size * 0.72)
    cradle_h = int(glyph_size * 0.32)
    draw.arc((cx - cradle_w // 2, body_y2 - cradle_h // 2,
              cx + cradle_w // 2, body_y2 - cradle_h // 2 + cradle_h),
             start=10, end=170, fill=color, width=line_w)
    stem_top = body_y2 - cradle_h // 2 + cradle_h // 2
    stem_bottom = stem_top + int(glyph_size * 0.16)
    draw.line((cx, stem_top, cx, stem_bottom), fill=color, width=line_w)
    base_w = int(glyph_size * 0.40)
    draw.line((cx - base_w // 2, stem_bottom, cx + base_w // 2, stem_bottom),
              fill=color, width=line_w)


def _mic_grille(draw, cx, cy, glyph_size, color):
    """Capsule with horizontal grille lines on the body — looks like a real mic."""
    body_w = int(glyph_size * 0.50)
    body_h = int(glyph_size * 0.66)
    body_x1 = cx - body_w // 2
    body_y1 = cy - body_h // 2 - int(glyph_size * 0.06)
    body_x2 = body_x1 + body_w
    body_y2 = body_y1 + body_h
    draw.rounded_rectangle((body_x1, body_y1, body_x2, body_y2),
                           radius=body_w // 2, fill=color)
    # Grille lines — drawn slightly darker on top of the body. Use the disc
    # background colour by punching transparency through… actually for icons
    # simpler: draw the grille as a contrasting stripe pattern using a slightly
    # lighter version of color (towards white).
    r, g, b = color
    grille = (min(255, r + 60), min(255, g + 60), min(255, b + 60))
    n_lines = 4
    margin_y = int(body_h * 0.20)
    inner_top = body_y1 + margin_y
    inner_bottom = body_y2 - margin_y
    spacing = (inner_bottom - inner_top) / max(1, n_lines - 1) if n_lines > 1 else 0
    inner_x1 = body_x1 + int(body_w * 0.18)
    inner_x2 = body_x2 - int(body_w * 0.18)
    line_w = max(2, glyph_size // 24)
    for i in range(n_lines):
        y = int(inner_top + i * spacing)
        draw.line((inner_x1, y, inner_x2, y), fill=grille, width=line_w)
    # Cradle
    cradle_w = int(glyph_size * 0.78)
    cradle_h = int(glyph_size * 0.36)
    arc_w = max(2, glyph_size // 20)
    draw.arc((cx - cradle_w // 2, body_y2 - cradle_h // 2,
              cx + cradle_w // 2, body_y2 - cradle_h // 2 + cradle_h),
             start=10, end=170, fill=color, width=arc_w)
    stem_top = body_y2 - cradle_h // 2 + cradle_h // 2
    stem_bottom = stem_top + int(glyph_size * 0.12)
    draw.line((cx, stem_top, cx, stem_bottom), fill=color, width=arc_w)


def _mic_podcast(draw, cx, cy, glyph_size, color):
    """Chunky podcast-style mic: tall rounded capsule with no stand."""
    body_w = int(glyph_size * 0.58)
    body_h = int(glyph_size * 0.84)
    body_x1 = cx - body_w // 2
    body_y1 = cy - body_h // 2
    body_x2 = body_x1 + body_w
    body_y2 = body_y1 + body_h
    draw.rounded_rectangle((body_x1, body_y1, body_x2, body_y2),
                           radius=body_w // 2, fill=color)
    # Add a horizontal "split" line near the top to suggest the mic head
    line_w = max(2, glyph_size // 22)
    split_y = body_y1 + int(body_h * 0.42)
    r, g, b = color
    split = (min(255, r + 60), min(255, g + 60), min(255, b + 60))
    inner_x1 = body_x1 + int(body_w * 0.18)
    inner_x2 = body_x2 - int(body_w * 0.18)
    draw.line((inner_x1, split_y, inner_x2, split_y),
              fill=split, width=line_w)


def _mic_modern_flat(draw, cx, cy, glyph_size, color):
    """Modern flat: rounded body + full bracket-shape stand (drawn as filled shape)."""
    # Body
    body_w = int(glyph_size * 0.44)
    body_h = int(glyph_size * 0.56)
    body_x1 = cx - body_w // 2
    body_y1 = cy - body_h // 2 - int(glyph_size * 0.10)
    body_x2 = body_x1 + body_w
    body_y2 = body_y1 + body_h
    draw.rounded_rectangle((body_x1, body_y1, body_x2, body_y2),
                           radius=body_w // 2, fill=color)
    # U-shaped bracket below: draw filled outer rounded rect minus inner rounded rect.
    bk_w = int(glyph_size * 0.74)
    bk_h = int(glyph_size * 0.34)
    bk_x1 = cx - bk_w // 2
    bk_y1 = body_y2 - bk_h // 4
    bk_x2 = bk_x1 + bk_w
    bk_y2 = bk_y1 + bk_h
    # outer
    bracket = Image.new("RGBA", (bk_w + 4, bk_h + 4), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bracket)
    bd.rounded_rectangle((2, 2, bk_w + 1, bk_h + 1),
                         radius=bk_w // 2, fill=color)
    # punch inner
    inner_pad = max(3, glyph_size // 14)
    bd.rounded_rectangle((2 + inner_pad, 2,
                          bk_w + 1 - inner_pad, bk_h + 1 - inner_pad),
                         radius=(bk_w // 2) - inner_pad,
                         fill=(0, 0, 0, 0))
    # Compose by alpha-blending bracket onto whatever the caller is drawing on.
    # We can't easily do this through ImageDraw; instead, paste using the
    # alpha channel via the underlying image. Pillow trick: walk back up to
    # the parent image via the draw object.
    parent = draw._image  # type: ignore[attr-defined]
    parent.alpha_composite(bracket, (bk_x1 - 2, bk_y1 - 2))
    # Short stand
    line_w = max(2, glyph_size // 22)
    stand_top = bk_y2 - inner_pad // 2
    stand_bottom = stand_top + int(glyph_size * 0.10)
    draw.rectangle((cx - line_w, stand_top,
                    cx + line_w, stand_bottom), fill=color)


def _waveform_symmetric(draw: ImageDraw.ImageDraw, cx: int, cy: int,
                        n: int, bar_w: int, gap: int, max_h: int,
                        levels: list[float], color, radius: int = 0) -> None:
    """Symmetric (mirror) waveform centred at ``cy`` — modern equalizer feel."""
    total_w = n * bar_w + (n - 1) * gap
    start_x = cx - total_w // 2
    for i, lvl in enumerate(levels):
        h = max(2, int(max_h * max(0.08, min(1.0, lvl))))
        x1 = start_x + i * (bar_w + gap)
        y1 = cy - h
        y2 = cy + h
        draw.rounded_rectangle((x1, y1, x1 + bar_w, y2), radius=radius, fill=color)


# =============================================================================
# Variant A — Modern Minimalist  (cool dark card, mint accent)
# =============================================================================
A_PALETTE = {
    "card_fill":  (28, 32, 40, 235),   # near-black translucent
    "card_edge":  (255, 255, 255, 22),
    "mic":        (240, 240, 245),
    "wave":       (110, 220, 170),     # mint
    "wave_off":   (110, 220, 170, 90),
    "label":      (228, 232, 240),
    "sub":        (160, 168, 180),
    "dot":        (255, 90, 90),
}


def render_overlay_A(state: str, levels: list[float]) -> Image.Image:
    W, H = 220, 76
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _rounded_rect(d, (0, 0, W - 1, H - 1), radius=18,
                  fill=A_PALETTE["card_fill"],
                  outline=A_PALETTE["card_edge"], width=1)

    # Mic on the left in a small subtle disc
    cx_mic = 28
    cy_mic = H // 2
    _rounded_rect(d, (8, 10, 50, H - 10), radius=14,
                  fill=(255, 255, 255, 14))
    _mic_glyph(d, cx_mic, cy_mic, glyph_size=42, color=A_PALETTE["mic"])

    # Symmetric waveform in the centre
    wave_cx = 116
    wave_cy = 26
    if state == "RECORDING":
        _waveform_symmetric(d, wave_cx, wave_cy, n=9, bar_w=4, gap=3,
                            max_h=14, levels=levels, color=A_PALETTE["wave"], radius=2)
    else:
        _waveform_symmetric(d, wave_cx, wave_cy, n=9, bar_w=4, gap=3,
                            max_h=4, levels=[0.15] * 9,
                            color=A_PALETTE["wave_off"], radius=2)

    # Status line under the waveform
    label_text, sub_text, dot = {
        "IDLE":         ("待機",     "Ready",         False),
        "RECORDING":    ("錄音中",   "Recording…",    True),
        "TRANSCRIBING": ("辨識中",   "Transcribing…", False),
        "POLISHING":    ("潤稿中",   "Polishing…",    False),
        "INJECTING":    ("貼上中",   "Pasting…",      False),
        "ERROR":        ("錯誤",     "Error",         False),
    }[state]
    f_label = _font(13, bold=True)
    f_sub   = _font(10)
    label_x = 64
    label_y = H - 28
    if dot:
        d.ellipse((label_x, label_y + 6, label_x + 8, label_y + 14),
                  fill=A_PALETTE["dot"])
        label_x += 12
    d.text((label_x, label_y), label_text, font=f_label, fill=A_PALETTE["label"])
    d.text((label_x + 56, label_y + 2), sub_text, font=f_sub, fill=A_PALETTE["sub"])
    return _drop_shadow(img, blur=10, offset=(0, 4), color=(0, 0, 0, 110))


def render_tray_A(state: str) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bg = (28, 32, 40) if state != "RECORDING" else (200, 60, 60)
    d.ellipse((2, 2, size - 2, size - 2), fill=bg)
    glyph = (240, 240, 245) if state != "RECORDING" else (255, 230, 110)
    _mic_glyph(d, size // 2, size // 2 + 2, glyph_size=42, color=glyph)
    if state == "RECORDING":
        # tiny green wave at top
        _waveform_symmetric(d, size // 2, 12, n=5, bar_w=3, gap=2,
                            max_h=5, levels=[0.4, 0.7, 1.0, 0.7, 0.4],
                            color=A_PALETTE["wave"], radius=1)
    return img


# =============================================================================
# Variant B — Warm Polished  (current palette, modernised)
# =============================================================================
B_PALETTE = {
    "card_fill":   (255, 248, 232, 240),  # cream
    "card_edge":   (160, 110, 70, 80),
    "mic_disc":    (244, 213, 108),       # butter
    "mic_disc_rec":(195, 83, 53),         # terracotta
    "mic":         (62, 42, 23),
    "mic_rec":     (250, 220, 80),
    "wave":        (110, 180, 90),        # warm green
    "wave_off":    (140, 130, 110, 130),
    "label":       (62, 42, 23),
    "sub":         (130, 100, 70),
    "highlight":   (255, 255, 255, 80),
}


def render_overlay_B(state: str, levels: list[float]) -> Image.Image:
    W, H = 220, 80
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _rounded_rect(d, (0, 0, W - 1, H - 1), radius=18,
                  fill=B_PALETTE["card_fill"],
                  outline=B_PALETTE["card_edge"], width=1)

    # Left mic disc
    disc_x1, disc_y1 = 10, 10
    disc_x2, disc_y2 = 70, H - 10
    disc_color = (B_PALETTE["mic_disc_rec"]
                  if state == "RECORDING" else B_PALETTE["mic_disc"])
    d.ellipse((disc_x1, disc_y1, disc_x2, disc_y2), fill=disc_color)
    # subtle top highlight on the disc
    d.ellipse((disc_x1 + 6, disc_y1 + 4, disc_x2 - 6, disc_y1 + 22),
              fill=B_PALETTE["highlight"])

    glyph_color = (B_PALETTE["mic_rec"]
                   if state == "RECORDING" else B_PALETTE["mic"])
    _mic_glyph(d, (disc_x1 + disc_x2) // 2, (disc_y1 + disc_y2) // 2 + 1,
               glyph_size=46, color=glyph_color)

    # Waveform top-right
    wave_cx, wave_cy = 145, 26
    if state == "RECORDING":
        _waveform_symmetric(d, wave_cx, wave_cy, n=9, bar_w=5, gap=3,
                            max_h=14, levels=levels,
                            color=B_PALETTE["wave"], radius=2)
    else:
        _waveform_symmetric(d, wave_cx, wave_cy, n=9, bar_w=5, gap=3,
                            max_h=4, levels=[0.2] * 9,
                            color=B_PALETTE["wave_off"], radius=2)

    # Bottom status label inside its own thin pill
    pill_x1, pill_y1 = 80, H - 28
    pill_x2, pill_y2 = W - 10, H - 8
    _rounded_rect(d, (pill_x1, pill_y1, pill_x2, pill_y2), radius=10,
                  fill=disc_color)
    label_text = {
        "IDLE":         "待機",
        "RECORDING":    "● 錄音中",
        "TRANSCRIBING": "辨識中…",
        "POLISHING":    "潤稿中…",
        "INJECTING":    "貼上中…",
        "ERROR":        "錯誤",
    }[state]
    f = _font(12, bold=True)
    bbox = d.textbbox((0, 0), label_text, font=f)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    d.text(((pill_x1 + pill_x2) // 2 - tw // 2,
            (pill_y1 + pill_y2) // 2 - th // 2 - 1),
           label_text, font=f, fill=B_PALETTE["label"])
    return _drop_shadow(img, blur=8, offset=(0, 3), color=(80, 50, 20, 100))


def render_tray_B(state: str) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bg = (B_PALETTE["mic_disc_rec"] if state == "RECORDING"
          else B_PALETTE["mic_disc"])
    d.ellipse((2, 2, size - 2, size - 2), fill=bg)
    # highlight
    d.ellipse((10, 6, size - 10, 22), fill=B_PALETTE["highlight"])
    glyph = (B_PALETTE["mic_rec"] if state == "RECORDING" else B_PALETTE["mic"])
    _mic_glyph(d, size // 2, size // 2 + 2, glyph_size=44, color=glyph)
    if state == "RECORDING":
        _waveform_symmetric(d, size // 2, 12, n=5, bar_w=3, gap=2,
                            max_h=5, levels=[0.4, 0.7, 1.0, 0.7, 0.4],
                            color=B_PALETTE["wave"], radius=1)
    return img


# =============================================================================
# Variant C — Pill Horizontal  (slim, waveform-led)
# =============================================================================
C_PALETTE = {
    "card_fill":  (24, 26, 30, 235),
    "card_edge":  (255, 255, 255, 18),
    "mic_bg_idle":(80, 88, 102),
    "mic_bg_rec": (220, 70, 70),
    "mic":        (245, 246, 250),
    "wave":       (96, 220, 160),
    "wave_off":   (110, 130, 150, 130),
    "label":      (235, 238, 244),
    "sub":        (160, 170, 185),
}


def render_overlay_C(state: str, levels: list[float]) -> Image.Image:
    W, H = 240, 56
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _rounded_rect(d, (0, 0, W - 1, H - 1), radius=H // 2,
                  fill=C_PALETTE["card_fill"],
                  outline=C_PALETTE["card_edge"], width=1)

    # Tiny mic disc on the far left
    disc_r = (H - 10) // 2
    cx_mic = 6 + disc_r
    cy_mic = H // 2
    bg = (C_PALETTE["mic_bg_rec"] if state == "RECORDING"
          else C_PALETTE["mic_bg_idle"])
    d.ellipse((cx_mic - disc_r, cy_mic - disc_r,
               cx_mic + disc_r, cy_mic + disc_r), fill=bg)
    _mic_glyph(d, cx_mic, cy_mic + 1, glyph_size=30, color=C_PALETTE["mic"])

    # Waveform — main visual area
    wave_cx, wave_cy = 130, H // 2
    if state == "RECORDING":
        _waveform_symmetric(d, wave_cx, wave_cy, n=11, bar_w=4, gap=3,
                            max_h=14, levels=levels,
                            color=C_PALETTE["wave"], radius=2)
    else:
        _waveform_symmetric(d, wave_cx, wave_cy, n=11, bar_w=4, gap=3,
                            max_h=3, levels=[0.2] * 11,
                            color=C_PALETTE["wave_off"], radius=2)

    # Status text on the right
    label_text = {
        "IDLE":         "待機",
        "RECORDING":    "錄音中",
        "TRANSCRIBING": "辨識",
        "POLISHING":    "潤稿",
        "INJECTING":    "貼上",
        "ERROR":        "錯誤",
    }[state]
    f = _font(12, bold=True)
    bbox = d.textbbox((0, 0), label_text, font=f)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    d.text((W - tw - 14, (H - th) // 2 - 1),
           label_text, font=f, fill=C_PALETTE["label"])
    return _drop_shadow(img, blur=10, offset=(0, 4), color=(0, 0, 0, 130))


def render_tray_C(state: str) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # rounded square instead of circle for a fresher look
    bg = (24, 26, 30) if state != "RECORDING" else (200, 60, 60)
    d.rounded_rectangle((2, 2, size - 2, size - 2), radius=14, fill=bg)
    glyph = (245, 246, 250) if state != "RECORDING" else (255, 230, 110)
    _mic_glyph(d, size // 2, size // 2 + 2, glyph_size=42, color=glyph)
    if state == "RECORDING":
        _waveform_symmetric(d, size // 2, 11, n=5, bar_w=3, gap=2,
                            max_h=5, levels=[0.4, 0.7, 1.0, 0.7, 0.4],
                            color=C_PALETTE["wave"], radius=1)
    return img


# =============================================================================
# Variant D — HYBRID: B's warm palette + C's pill shape, large status on right
# =============================================================================
D_PALETTE = {
    "card_fill":   (255, 248, 232, 245),   # cream
    "card_edge":   (160, 110, 70, 90),
    "mic":         (62, 42, 23),
    "mic_rec":     (250, 220, 80),
    "wave":        (110, 180, 90),
    "wave_off":    (150, 130, 100, 130),
    "label":       (62, 42, 23),
    "highlight":   (255, 255, 255, 90),
}

# Per-state disc colour so a glance at the colour tells you the state without
# having to read the text. Mirrors the original tray_icons.py palette.
D_DISC_COLOR = {
    "IDLE":         (244, 213, 108),  # butter
    "RECORDING":    (195, 83, 53),    # terracotta
    "TRANSCRIBING": (215, 148, 55),   # warm amber
    "POLISHING":    (215, 148, 55),   # warm amber (same family as transcribing)
    "INJECTING":    (138, 165, 97),   # olive
    "ERROR":        (158, 138, 115),  # warm grey
}

D_LABEL = {
    "IDLE":         "待機",
    "RECORDING":    "錄音中",
    "TRANSCRIBING": "辨識中",
    "POLISHING":    "潤稿中",
    "INJECTING":    "貼上中",
    "ERROR":        "錯誤",
}


def render_overlay_D(state: str, levels: list[float]) -> Image.Image:
    # Compact mode: H stays at 64 (unchanged) but text doubles to 32px bold,
    # mic / waveform / text are pushed close together with minimal padding.
    H = 64
    label_text = D_LABEL[state]
    f = _font(32, bold=True)

    # Build layout from the actual text size so the pill snug-fits the content.
    GAP_DISC_WAVE = 15    # user-specified middle whitespace
    GAP_WAVE_TEXT = 15
    LEFT_PAD = 6
    RIGHT_PAD = 14
    disc_r = (H - 10) // 2

    # Bigger waveform too, since the text is now bigger.
    n_bars = 7
    bar_w = 5
    bar_gap = 4
    wave_w = n_bars * bar_w + (n_bars - 1) * bar_gap

    # Probe text size (bbox needs an image but we can use a throwaway).
    tmp = Image.new("RGBA", (1, 1))
    td = ImageDraw.Draw(tmp)
    bbox = td.textbbox((0, 0), label_text, font=f)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    W = LEFT_PAD + 2 * disc_r + GAP_DISC_WAVE + wave_w + GAP_WAVE_TEXT + tw + RIGHT_PAD

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Pill card (cream warmth from B, full-radius ends from C)
    _rounded_rect(d, (0, 0, W - 1, H - 1), radius=H // 2,
                  fill=D_PALETTE["card_fill"],
                  outline=D_PALETTE["card_edge"], width=1)

    # Mic disc on left
    cx_mic = LEFT_PAD + disc_r
    cy_mic = H // 2
    disc_color = D_DISC_COLOR.get(state, D_DISC_COLOR["IDLE"])
    d.ellipse((cx_mic - disc_r, cy_mic - disc_r,
               cx_mic + disc_r, cy_mic + disc_r), fill=disc_color)
    glyph_color = (D_PALETTE["mic_rec"]
                   if state == "RECORDING" else D_PALETTE["mic"])
    # Bigger mic glyph — fills more of the disc so it reads clearly at a glance.
    # disc diameter is 2*disc_r = 54; 48 leaves a ~3px margin on each side.
    _mic_glyph(d, cx_mic, cy_mic + 1, glyph_size=48, color=glyph_color)

    # Waveform sits right of the disc, vertically centred
    wave_cx = cx_mic + disc_r + GAP_DISC_WAVE + wave_w // 2
    wave_cy = H // 2
    use_levels = (levels[:n_bars] if state == "RECORDING"
                  else [0.18] * n_bars)
    color = (D_PALETTE["wave"] if state == "RECORDING"
             else D_PALETTE["wave_off"])
    max_h = 16 if state == "RECORDING" else 3
    _waveform_symmetric(d, wave_cx, wave_cy, n=n_bars, bar_w=bar_w, gap=bar_gap,
                        max_h=max_h, levels=use_levels, color=color, radius=2)

    # Big status text on the right (32px bold). y aligned by font ascent.
    text_x = cx_mic + disc_r + GAP_DISC_WAVE + wave_w + GAP_WAVE_TEXT
    text_y = (H - th) // 2 - bbox[1]
    d.text((text_x, text_y), label_text, font=f, fill=D_PALETTE["label"])

    return _drop_shadow(img, blur=10, offset=(0, 4), color=(80, 50, 20, 110))


def render_tray_D(state: str) -> Image.Image:
    """Tray icon — circular, colour shifts per state for at-a-glance feedback."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bg = D_DISC_COLOR.get(state, D_DISC_COLOR["IDLE"])
    d.ellipse((2, 2, size - 2, size - 2), fill=bg)
    glyph = (D_PALETTE["mic_rec"] if state == "RECORDING"
             else D_PALETTE["mic"])
    _mic_glyph(d, size // 2, size // 2 + 2, glyph_size=44, color=glyph)
    if state == "RECORDING":
        _waveform_symmetric(d, size // 2, 12, n=5, bar_w=3, gap=2,
                            max_h=5, levels=[0.4, 0.7, 1.0, 0.7, 0.4],
                            color=D_PALETTE["wave"], radius=1)
    return img


# =============================================================================
# Composer — paste mockups onto a contact-sheet PNG so user can scan all-at-once
# =============================================================================

def _contact_sheet() -> Path:
    """Build a single PNG showing all variants side-by-side for quick review."""
    levels_rec = [0.4, 0.7, 1.0, 0.85, 0.55, 0.35, 0.7, 0.9, 0.6, 0.45, 0.5]
    states = ["IDLE", "RECORDING"]

    # Per-variant render dict
    variants = {
        "A_modern_minimalist": (render_overlay_A, render_tray_A),
        "B_warm_polished":     (render_overlay_B, render_tray_B),
        "C_pill_horizontal":   (render_overlay_C, render_tray_C),
    }

    for name, (overlay_fn, tray_fn) in variants.items():
        for st in states:
            ov = overlay_fn(st, levels_rec[: 11 if "C" in name else 9])
            (OUT_DIR / f"{name}_overlay_{st.lower()}.png").write_bytes(_to_png_bytes(ov))
        for st in ["IDLE", "RECORDING"]:
            tr = tray_fn(st)
            (OUT_DIR / f"{name}_tray_{st.lower()}.png").write_bytes(_to_png_bytes(tr))

    # Contact sheet (3 rows × 2 columns of overlays + tray strip on the right)
    pad = 24
    bg_color = (245, 244, 240, 255)
    rowh = 170  # was 110 — overlay + drop shadow + state label all need room
    sheet_w = 1100
    sheet_h = pad + rowh * 3 + pad
    sheet = Image.new("RGBA", (sheet_w, sheet_h), bg_color)
    d = ImageDraw.Draw(sheet)
    title_font = _font(18, bold=True)
    body_font = _font(12)

    rows = [
        ("A · Modern Minimalist (深色卡片 + mint 對稱波形)",
         "A_modern_minimalist"),
        ("B · Warm Polished (保留現有暖色 vibe，加陰影/圓角/高光)",
         "B_warm_polished"),
        ("C · Pill Horizontal (細長膠囊，波形為主視覺)",
         "C_pill_horizontal"),
    ]
    for i, (title, key) in enumerate(rows):
        y0 = pad + i * rowh
        d.text((pad, y0 + 2), title, font=title_font, fill=(40, 40, 50))
        idle = Image.open(OUT_DIR / f"{key}_overlay_idle.png")
        rec  = Image.open(OUT_DIR / f"{key}_overlay_recording.png")
        tray_idle = Image.open(OUT_DIR / f"{key}_tray_idle.png")
        tray_rec  = Image.open(OUT_DIR / f"{key}_tray_recording.png")
        # Place overlays + label
        sheet.alpha_composite(idle, (pad, y0 + 28))
        d.text((pad, y0 + 28 + idle.height + 2), "IDLE", font=body_font, fill=(80, 80, 90))
        sheet.alpha_composite(rec, (pad + idle.width + 24, y0 + 28))
        d.text((pad + idle.width + 24, y0 + 28 + rec.height + 2),
               "RECORDING", font=body_font, fill=(80, 80, 90))
        # Tray icons on the right
        tx = sheet_w - pad - tray_idle.width - 16 - tray_rec.width
        sheet.alpha_composite(tray_idle, (tx, y0 + 32))
        sheet.alpha_composite(tray_rec, (tx + tray_idle.width + 16, y0 + 32))
        d.text((tx, y0 + 32 + tray_idle.height + 2),
               "tray idle / rec (64×64)", font=body_font, fill=(80, 80, 90))

    sheet_path = OUT_DIR / "contact_sheet.png"
    sheet.convert("RGB").save(sheet_path, "PNG", optimize=True)
    return sheet_path


def _to_png_bytes(img: Image.Image) -> bytes:
    import io
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _hybrid_preview() -> Path:
    """Render Variant D across all 6 pipeline states for a focused preview."""
    levels_rec = [0.45, 0.7, 1.0, 0.85, 0.6, 0.4, 0.8, 0.95, 0.65, 0.5, 0.55]
    states = ["IDLE", "RECORDING", "TRANSCRIBING", "POLISHING",
              "INJECTING", "ERROR"]

    pad = 24
    title_h = 36
    rowh = 90  # overlay 64 + shadow + label
    sheet_w = 700
    sheet_h = pad + title_h + rowh * len(states) + pad
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (245, 244, 240, 255))
    d = ImageDraw.Draw(sheet)

    title = "D · Hybrid (compact) — B 暖色 + C 膠囊，狀態文字 32px 在右"
    d.text((pad, pad), title, font=_font(18, bold=True), fill=(40, 40, 50))

    tray_idle = render_tray_D("IDLE")
    tray_rec = render_tray_D("RECORDING")
    sheet.alpha_composite(tray_idle, (sheet_w - pad - tray_idle.width, pad))
    sheet.alpha_composite(tray_rec,
                          (sheet_w - pad - tray_idle.width - tray_rec.width - 12,
                           pad))

    body_font = _font(12)
    for i, st in enumerate(states):
        y0 = pad + title_h + i * rowh
        ov = render_overlay_D(st, levels_rec)
        sheet.alpha_composite(ov, (pad, y0))
        d.text((pad + ov.width + 16, y0 + 16),
               st, font=_font(13, bold=True), fill=(60, 60, 70))

    out = OUT_DIR / "D_hybrid_preview.png"
    sheet.convert("RGB").save(out, "PNG", optimize=True)

    # Also save individual D PNGs for reuse
    for st in states:
        ov = render_overlay_D(st, levels_rec)
        (OUT_DIR / f"D_hybrid_overlay_{st.lower()}.png").write_bytes(_to_png_bytes(ov))
    (OUT_DIR / "D_hybrid_tray_idle.png").write_bytes(_to_png_bytes(tray_idle))
    (OUT_DIR / "D_hybrid_tray_recording.png").write_bytes(_to_png_bytes(tray_rec))
    return out


def _mic_styles_preview() -> Path:
    """Render the 6 mic glyph styles in IDLE + RECORDING state inside a disc,
    plus the corresponding full overlay pill, for side-by-side comparison."""
    styles = [
        ("capsule_arch",  "1 · capsule_arch (現有)"),
        ("solid_filled",  "2 · solid_filled (粗體實心)"),
        ("outline",       "3 · outline (線條風)"),
        ("grille",        "4 · grille (有網孔細節)"),
        ("podcast",       "5 · podcast (Podcast 圓胖)"),
        ("modern_flat",   "6 · modern_flat (現代扁平)"),
    ]
    levels_rec = [0.45, 0.7, 1.0, 0.85, 0.6, 0.4, 0.8]

    pad = 24
    disc_size = 100   # blown up for clarity
    rowh = 130
    sheet_w = 1180
    sheet_h = pad + 32 + rowh * len(styles) + pad
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (245, 244, 240, 255))
    d = ImageDraw.Draw(sheet)

    title = "麥克風圖示 6 種風格比較（左：放大 disc / 右：完整 overlay IDLE+RECORDING）"
    d.text((pad, pad), title, font=_font(18, bold=True), fill=(40, 40, 50))

    for i, (style, label) in enumerate(styles):
        y0 = pad + 32 + i * rowh
        d.text((pad, y0 + 4), label, font=_font(15, bold=True), fill=(60, 60, 70))

        # Render two enlarged discs (idle yellow + recording terracotta)
        for j, (state_label, disc_color, glyph_color) in enumerate([
            ("IDLE",      D_DISC_COLOR["IDLE"],      D_PALETTE["mic"]),
            ("RECORDING", D_DISC_COLOR["RECORDING"], D_PALETTE["mic_rec"]),
        ]):
            disc_img = Image.new("RGBA", (disc_size, disc_size), (0, 0, 0, 0))
            dd = ImageDraw.Draw(disc_img)
            dd.ellipse((0, 0, disc_size - 1, disc_size - 1), fill=disc_color)
            # Use 0.88 of disc as glyph size (matches our disc_r=27 → glyph 48 ratio)
            glyph_px = int(disc_size * 0.88)
            _mic_glyph(dd, disc_size // 2, disc_size // 2 + 1,
                       glyph_size=glyph_px, color=glyph_color, style=style)
            x = pad + j * (disc_size + 16)
            sheet.alpha_composite(disc_img, (x, y0 + 28))
            d.text((x, y0 + 28 + disc_size + 2), state_label,
                   font=_font(11), fill=(100, 100, 110))

        # Render the actual overlay pill (idle + recording) with this mic style
        # by temporarily swapping the global default style.
        idle_overlay = _render_overlay_with_mic_style("IDLE", levels_rec, style)
        rec_overlay  = _render_overlay_with_mic_style("RECORDING", levels_rec, style)
        ox = pad + 2 * (disc_size + 16) + 24
        sheet.alpha_composite(idle_overlay, (ox, y0 + 30))
        sheet.alpha_composite(rec_overlay,
                              (ox, y0 + 30 + idle_overlay.height + 6))

    out = OUT_DIR / "mic_styles_preview.png"
    sheet.convert("RGB").save(out, "PNG", optimize=True)
    return out


def _render_overlay_with_mic_style(state: str, levels: list[float], style: str) -> Image.Image:
    """Same as render_overlay_D but with explicit mic style."""
    H = 64
    label_text = D_LABEL[state]
    f = _font(32, bold=True)

    GAP_DISC_WAVE = 15
    GAP_WAVE_TEXT = 15
    LEFT_PAD = 6
    RIGHT_PAD = 14
    disc_r = (H - 10) // 2

    n_bars = 7
    bar_w = 5
    bar_gap = 4
    wave_w = n_bars * bar_w + (n_bars - 1) * bar_gap

    tmp = Image.new("RGBA", (1, 1))
    td = ImageDraw.Draw(tmp)
    bbox = td.textbbox((0, 0), label_text, font=f)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    W = LEFT_PAD + 2 * disc_r + GAP_DISC_WAVE + wave_w + GAP_WAVE_TEXT + tw + RIGHT_PAD
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _rounded_rect(d, (0, 0, W - 1, H - 1), radius=H // 2,
                  fill=D_PALETTE["card_fill"],
                  outline=D_PALETTE["card_edge"], width=1)
    cx_mic = LEFT_PAD + disc_r
    cy_mic = H // 2
    disc_color = D_DISC_COLOR.get(state, D_DISC_COLOR["IDLE"])
    d.ellipse((cx_mic - disc_r, cy_mic - disc_r,
               cx_mic + disc_r, cy_mic + disc_r), fill=disc_color)
    glyph_color = (D_PALETTE["mic_rec"]
                   if state == "RECORDING" else D_PALETTE["mic"])
    _mic_glyph(d, cx_mic, cy_mic + 1, glyph_size=48,
               color=glyph_color, style=style)

    wave_cx = cx_mic + disc_r + GAP_DISC_WAVE + wave_w // 2
    wave_cy = H // 2
    use_levels = (levels[:n_bars] if state == "RECORDING"
                  else [0.18] * n_bars)
    color = (D_PALETTE["wave"] if state == "RECORDING"
             else D_PALETTE["wave_off"])
    max_h = 16 if state == "RECORDING" else 3
    _waveform_symmetric(d, wave_cx, wave_cy, n=n_bars, bar_w=bar_w, gap=bar_gap,
                        max_h=max_h, levels=use_levels, color=color, radius=2)

    text_x = cx_mic + disc_r + GAP_DISC_WAVE + wave_w + GAP_WAVE_TEXT
    text_y = (H - th) // 2 - bbox[1]
    d.text((text_x, text_y), label_text, font=f, fill=D_PALETTE["label"])
    return _drop_shadow(img, blur=10, offset=(0, 4), color=(80, 50, 20, 110))


# =============================================================================
# Variant E — Reference-image style: pill card with tinted edge, white mic on
# coloured disc, dots indicator (or waveform when recording), big CJK status.
# Each state has a distinct disc + matching subtle card edge.
# =============================================================================
E_PALETTE = {
    "card_fill": (250, 246, 236, 250),  # warm cream
    "label":     (40, 32, 26),
    "mic_white": (255, 255, 255),
    "wave_rec":  (217, 74, 61),         # red waveform during recording
}

# Per-state disc colour, matching the reference image
E_DISC_COLOR = {
    "IDLE":         (58, 46, 37),       # deep charcoal-brown
    "RECORDING":    (217, 74, 61),      # red
    "TRANSCRIBING": (230, 138, 46),     # orange
    "POLISHING":    (90, 142, 197),     # blue
    "INJECTING":    (95, 161, 90),      # green
    "ERROR":        (138, 138, 138),    # mid grey
}

# Subtle outline tint per state (alpha-blended into cream edge)
E_BORDER_COLOR = {
    "IDLE":         (180, 160, 140, 120),
    "RECORDING":    (217, 74, 61, 160),
    "TRANSCRIBING": (230, 138, 46, 160),
    "POLISHING":    (90, 142, 197, 160),
    "INJECTING":    (95, 161, 90, 160),
    "ERROR":        (160, 160, 160, 140),
}

# Dot indicator colour (mirrors disc but slightly muted for non-RECORDING)
E_DOT_COLOR = {
    "IDLE":         (130, 110, 95),
    "TRANSCRIBING": (230, 138, 46),
    "POLISHING":    (90, 142, 197),
    "INJECTING":    (95, 161, 90),
    "ERROR":        (160, 160, 160),
}

E_LABEL = D_LABEL  # same Chinese labels as variant D


def _dots_indicator(draw: ImageDraw.ImageDraw, cx: int, cy: int,
                    n: int, dot_r: int, gap: int,
                    color: tuple[int, int, int]) -> None:
    """Draw N small filled dots horizontally, centred on (cx, cy)."""
    total_w = n * (dot_r * 2) + (n - 1) * gap
    start_x = cx - total_w // 2
    for i in range(n):
        x = start_x + i * (dot_r * 2 + gap)
        draw.ellipse((x, cy - dot_r, x + dot_r * 2, cy + dot_r),
                     fill=color)


def render_overlay_E(state: str, levels: list[float]) -> Image.Image:
    """Reference-image variant: cream pill, white mic on coloured disc, dots
    or waveform in middle, big bold CJK label on right, tinted edge per state."""
    H = 64
    label_text = E_LABEL[state]
    f = _font(32, bold=True)

    GAP_DISC_MID = 14
    GAP_MID_TEXT = 14
    LEFT_PAD = 6
    RIGHT_PAD = 18
    disc_r = (H - 10) // 2

    # Middle indicator width: 5 dots OR small waveform of similar width
    mid_w = 50

    tmp = Image.new("RGBA", (1, 1))
    td = ImageDraw.Draw(tmp)
    bbox = td.textbbox((0, 0), label_text, font=f)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    W = LEFT_PAD + 2 * disc_r + GAP_DISC_MID + mid_w + GAP_MID_TEXT + tw + RIGHT_PAD

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Pill card with state-tinted edge
    _rounded_rect(d, (0, 0, W - 1, H - 1), radius=H // 2,
                  fill=E_PALETTE["card_fill"],
                  outline=E_BORDER_COLOR.get(state, E_BORDER_COLOR["IDLE"]),
                  width=2)

    # Left coloured disc
    cx_mic = LEFT_PAD + disc_r
    cy_mic = H // 2
    disc_color = E_DISC_COLOR.get(state, E_DISC_COLOR["IDLE"])
    d.ellipse((cx_mic - disc_r, cy_mic - disc_r,
               cx_mic + disc_r, cy_mic + disc_r), fill=disc_color)
    # White mic glyph on top — solid_filled reads cleanest in small disc
    _mic_glyph(d, cx_mic, cy_mic + 1, glyph_size=46,
               color=E_PALETTE["mic_white"], style="solid_filled")

    # Middle area: dots OR recording waveform
    mid_cx = cx_mic + disc_r + GAP_DISC_MID + mid_w // 2
    mid_cy = H // 2
    if state == "RECORDING":
        n_bars = 7
        bar_w = 4
        bar_gap = 3
        _waveform_symmetric(d, mid_cx, mid_cy, n=n_bars, bar_w=bar_w, gap=bar_gap,
                            max_h=14, levels=levels[:n_bars],
                            color=E_PALETTE["wave_rec"], radius=2)
    else:
        _dots_indicator(d, mid_cx, mid_cy, n=5, dot_r=3, gap=6,
                        color=E_DOT_COLOR.get(state, E_DOT_COLOR["IDLE"]))

    # Big bold status text on right
    text_x = cx_mic + disc_r + GAP_DISC_MID + mid_w + GAP_MID_TEXT
    text_y = (H - th) // 2 - bbox[1]
    d.text((text_x, text_y), label_text, font=f, fill=E_PALETTE["label"])

    return _drop_shadow(img, blur=10, offset=(0, 4), color=(80, 50, 20, 100))


def render_tray_E(state: str) -> Image.Image:
    """Tray icon: coloured disc + white mic, no extra waveform overlay."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bg = E_DISC_COLOR.get(state, E_DISC_COLOR["IDLE"])
    d.ellipse((2, 2, size - 2, size - 2), fill=bg)
    _mic_glyph(d, size // 2, size // 2 + 2, glyph_size=42,
               color=E_PALETTE["mic_white"], style="solid_filled")
    return img


def _reference_preview() -> Path:
    """Compose an all-states preview matching the user's reference image:
    six rows of overlay pills (one per pipeline state), with tray icons in
    the top-right corner. Light cream background."""
    levels_rec = [0.45, 0.7, 1.0, 0.85, 0.6, 0.4, 0.8]
    states = ["IDLE", "RECORDING", "TRANSCRIBING", "POLISHING",
              "INJECTING", "ERROR"]

    pad = 32
    rowh = 110           # tall enough for 64px overlay + shadow + breathing room
    sheet_w = 1280
    title_h = 0          # reference image has no title
    sheet_h = pad + title_h + rowh * len(states) + pad
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (245, 242, 234, 255))
    d = ImageDraw.Draw(sheet)

    # Tray previews top-right (RECORDING + IDLE — matches reference layout)
    tray_idle = render_tray_E("IDLE")
    tray_rec = render_tray_E("RECORDING")
    sheet.alpha_composite(tray_rec,
                          (sheet_w - pad - tray_idle.width - 24 - tray_rec.width,
                           pad + 16))
    sheet.alpha_composite(tray_idle,
                          (sheet_w - pad - tray_idle.width, pad + 16))

    # State labels font
    label_font = _font(15, bold=True)

    for i, st in enumerate(states):
        y0 = pad + title_h + i * rowh
        ov = render_overlay_E(st, levels_rec)
        # Centre overlay vertically inside its row, indent from left
        sheet.alpha_composite(ov, (pad + 100, y0 + (rowh - ov.height) // 2))
        # State name on the right (ENGLISH, like the reference)
        d.text((pad + 100 + ov.width + 32,
                y0 + (rowh - 20) // 2),
               st, font=label_font, fill=(110, 110, 120))

    out = OUT_DIR / "E_reference_preview.png"
    sheet.convert("RGB").save(out, "PNG", optimize=True)

    # Also persist individual PNGs
    for st in states:
        ov = render_overlay_E(st, levels_rec)
        (OUT_DIR / f"E_reference_overlay_{st.lower()}.png").write_bytes(_to_png_bytes(ov))
    (OUT_DIR / "E_reference_tray_idle.png").write_bytes(_to_png_bytes(tray_idle))
    (OUT_DIR / "E_reference_tray_recording.png").write_bytes(_to_png_bytes(tray_rec))
    return out


def main() -> int:
    sheet = _contact_sheet()
    hybrid = _hybrid_preview()
    mic_styles = _mic_styles_preview()
    reference = _reference_preview()
    print(f"[OK] mockups in: {OUT_DIR}")
    print(f"[OK] contact sheet: {sheet}")
    print(f"[OK] hybrid preview: {hybrid}")
    print(f"[OK] mic styles preview: {mic_styles}")
    print(f"[OK] reference preview: {reference}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
