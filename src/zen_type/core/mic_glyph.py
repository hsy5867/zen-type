"""Mic glyph rendered from the Claude Design SVG paths.

The design's ``ZTMicGlyph`` (refer_doc/claude_design/.../shared.jsx) is a
24×24 viewBox SVG with three primitives, all using stroke-width 2 with
round caps:

1. Filled rounded rectangle — the mic body capsule
   ``<rect x=9 y=2.5 w=6 h=11 rx=3 fill=color>``
2. Stroked half-circle arc — the U-shaped support
   ``<path d="M5.5 11 a6.5 6.5 0 0 0 13 0">``
3. Stroked vertical stem — connector to the stand
   ``<path d="M12 17.5 v3.5">``

We draw those primitives with PIL at supersampled resolution, then resize
down with LANCZOS for smooth edges. Cached per ``(color, glyph_height)``.
"""

from __future__ import annotations

from threading import Lock


# === SVG geometry (Claude Design shared.jsx) ================================
_VIEWBOX = 24.0
_STROKE_W = 2.0
_SUPERSAMPLE = 4

_BODY = (9.0, 2.5, 15.0, 13.5)   # x0, y0, x1, y1
_BODY_RADIUS = 3.0
_ARC_CX, _ARC_CY, _ARC_R = 12.0, 11.0, 6.5
_STEM_X, _STEM_TOP, _STEM_BOT = 12.0, 17.5, 21.0


_cache_lock = Lock()
_tinted_cache: dict[tuple[tuple[int, int, int], int], object] = {}


def _draw_round_cap(draw, x: float, y: float, radius: float, fill) -> None:
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def get_glyph(color: tuple[int, int, int], glyph_height: int):
    """Return an RGBA Pillow image of the mic recoloured to ``color`` and
    sized to ``glyph_height`` × ``glyph_height``. Cached per (color, height)."""
    from PIL import Image, ImageDraw

    key = (color, int(glyph_height))
    with _cache_lock:
        cached = _tinted_cache.get(key)
        if cached is not None:
            return cached

    target = max(8, int(glyph_height))
    canvas = target * _SUPERSAMPLE
    scale = canvas / _VIEWBOX
    sw = _STROKE_W * scale
    cap_r = sw / 2.0

    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fill = color + (255,)

    # 1. Body capsule — filled rounded rectangle
    bx0, by0, bx1, by1 = (v * scale for v in _BODY)
    d.rounded_rectangle(
        (bx0, by0, bx1, by1), radius=_BODY_RADIUS * scale, fill=fill,
    )

    # 2. Half-circle U arc (bottom half: PIL angles 0°→180° clockwise from east)
    arc_bbox = (
        (_ARC_CX - _ARC_R) * scale, (_ARC_CY - _ARC_R) * scale,
        (_ARC_CX + _ARC_R) * scale, (_ARC_CY + _ARC_R) * scale,
    )
    d.arc(arc_bbox, start=0, end=180, fill=fill, width=max(1, int(round(sw))))
    # Round caps at arc endpoints (5.5, 11) and (18.5, 11)
    _draw_round_cap(d, (_ARC_CX - _ARC_R) * scale, _ARC_CY * scale, cap_r, fill)
    _draw_round_cap(d, (_ARC_CX + _ARC_R) * scale, _ARC_CY * scale, cap_r, fill)

    # 3. Vertical stem — pill-shaped (rounded rect with full corner radius
    #    gives the SVG's round line caps automatically)
    sx = _STEM_X * scale
    d.rounded_rectangle(
        (sx - cap_r, _STEM_TOP * scale, sx + cap_r, _STEM_BOT * scale),
        radius=cap_r, fill=fill,
    )

    # Downsample with LANCZOS for clean anti-aliased edges
    out = img.resize((target, target), Image.LANCZOS)

    with _cache_lock:
        _tinted_cache[key] = out
    return out


def paste_mic(parent, cx: int, cy: int, glyph_height: int,
              color: tuple[int, int, int]) -> None:
    """Composite the mic glyph onto ``parent`` (RGBA Pillow image) centred
    on (cx, cy) at the given height in pixels."""
    glyph = get_glyph(color, glyph_height)
    gw, gh = glyph.size
    parent.alpha_composite(glyph, (cx - gw // 2, cy - gh // 2))
