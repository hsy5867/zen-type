"""Mic glyph loader.

The mic shape is taken VERBATIM from the user's reference image
(``zen_type/assets/mic_reference.png``) rather than re-drawn with PIL
primitives. This guarantees the silhouette matches the reference exactly —
no more iterating on `arc_w`, `body_h`, `gap` numerics that never quite
look right.

Usage::

    from zen_type.core.mic_glyph import paste_mic
    paste_mic(parent_img, cx, cy, glyph_height, color)

The reference file is loaded once and cached. Tinted/resized variants
are cached per (color, glyph_height) so repeated overlay/tray renders
don't redo the alpha conversion.
"""

from __future__ import annotations

import sys
from pathlib import Path
from threading import Lock


def _resolve_asset_path() -> Path:
    """Locate ``mic_reference.png`` whether running from source or PyInstaller
    onefile (which extracts the package under ``sys._MEIPASS``)."""
    base = Path(getattr(sys, "_MEIPASS", None)
                or Path(__file__).resolve().parent.parent.parent)
    # frozen: <_MEIPASS>/zen_type/assets/mic_reference.png
    # source: <repo>/src/zen_type/assets/mic_reference.png
    candidates = [
        base / "zen_type" / "assets" / "mic_reference.png",
        Path(__file__).resolve().parent.parent / "assets" / "mic_reference.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"mic_reference.png not found. Looked in: {[str(c) for c in candidates]}"
    )


_silhouette_lock = Lock()
_silhouette = None      # tuple[Image.Image, int, int]: (alpha mask, w, h)
_tinted_cache: dict[tuple[tuple[int, int, int], int], object] = {}


def _load_silhouette():
    """Return (alpha_image_L, width, height) cropped tightly to the mic
    silhouette. ``alpha_image_L`` is a single-channel mask where 255 = mic ink,
    0 = background.

    Two structural transforms are applied to the raw reference so the rendered
    glyph reads correctly at small sizes:

    1. **Body floodfill** — the reference draws the mic body as a hollow
       capsule outline. We floodfill its interior so the body is solid (the
       user wants the body to read as a filled silhouette, not a ring).
    2. **Stroke dilation** — at the native 1254×1254 resolution, strokes are
       ~35 px thick. After resizing to a 36-px-tall overlay glyph that becomes
       ~1.5 px and looks anaemic. We dilate the source mask before caching so
       strokes survive the downscale at all target sizes.
    """
    global _silhouette
    with _silhouette_lock:
        if _silhouette is not None:
            return _silhouette
        from PIL import Image, ImageDraw, ImageFilter
        path = _resolve_asset_path()
        src = Image.open(path).convert("L")
        # Binarise: dark (mic ink) → 255, light (bg) → 0
        bw = src.point(lambda v: 255 if v < 128 else 0).convert("L")

        # Floodfill body interior. The body is a closed capsule; its interior
        # is a connected pool of bg (0) pixels surrounded by mic ink (255).
        # Seed at ~22% down from the silhouette top, on the centre line —
        # always inside the body for any reasonable mic icon.
        bbox = bw.getbbox()
        if bbox is None:
            raise RuntimeError("mic_reference.png has no dark pixels")
        seed_x = (bbox[0] + bbox[2]) // 2
        seed_y = bbox[1] + (bbox[3] - bbox[1]) * 22 // 100
        # floodfill replaces the bg pool reachable from (seed_x, seed_y) with
        # mic ink (255). It stops at the body outline because outline pixels
        # already equal 255 and the threshold (10) treats anything ≥ 10 from
        # the seed value (0) as a boundary.
        ImageDraw.floodfill(bw, (seed_x, seed_y), value=255, thresh=10)

        # Dilate strokes so they remain readable after downscale. MaxFilter(N)
        # adds (N-1)/2 px on each side; 11 → +5 px → strokes ~45 px native →
        # ~2 px at a 36-px-tall overlay, ~3 px at a 64 px tray.
        bw = bw.filter(ImageFilter.MaxFilter(11))

        # Re-crop after fill+dilate (silhouette may have grown slightly)
        bbox = bw.getbbox()
        cropped = bw.crop(bbox)
        _silhouette = (cropped, cropped.size[0], cropped.size[1])
        return _silhouette


def get_glyph(color: tuple[int, int, int], glyph_height: int):
    """Return an RGBA Pillow image of the mic recoloured to ``color`` and
    resized so its height equals ``glyph_height`` (preserves aspect ratio).
    Cached per (color, glyph_height)."""
    from PIL import Image

    key = (color, int(glyph_height))
    cached = _tinted_cache.get(key)
    if cached is not None:
        return cached

    mask, src_w, src_h = _load_silhouette()
    # Preserve aspect ratio against requested height
    new_h = max(4, int(glyph_height))
    new_w = max(1, int(src_w * new_h / src_h))
    # Use NEAREST when target is very small (≤24px) so thin strokes don't
    # get blurred to invisibility; LANCZOS otherwise for clean edges.
    resample = Image.NEAREST if new_h <= 24 else Image.LANCZOS
    resized_mask = mask.resize((new_w, new_h), resample)
    # Build RGBA: solid `color` with the mask as alpha channel
    glyph = Image.new("RGBA", (new_w, new_h), color + (0,))
    solid = Image.new("RGBA", (new_w, new_h), color + (255,))
    glyph.paste(solid, (0, 0), resized_mask)
    _tinted_cache[key] = glyph
    return glyph


def paste_mic(parent, cx: int, cy: int, glyph_height: int,
              color: tuple[int, int, int]) -> None:
    """Composite the mic glyph onto ``parent`` (an RGBA Pillow Image)
    centred on (cx, cy) at the given height in pixels.

    `parent` is expected to be RGBA so alpha compositing works.
    """
    glyph = get_glyph(color, glyph_height)
    gw, gh = glyph.size
    parent.alpha_composite(glyph, (cx - gw // 2, cy - gh // 2))
