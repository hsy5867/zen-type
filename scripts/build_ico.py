"""Regenerate src/zen_type/assets/zen-type.ico from the in-app mic glyph.

Run this whenever the brand colours or mic geometry change::

    uv run python scripts/build_ico.py

The icon contains 7 sub-images (16/24/32/48/64/128/256). Smaller sizes use
a bright orange disc (#ff8a1e) so the icon pops in the Windows taskbar;
larger sizes use the Latte accent brown (#a8672f) to match the in-app
brand. The mic glyph is cropped to its tight visible bbox before
compositing so the visible mic — not the SVG viewBox padding — is what
fills the requested fraction of the disc.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw

from zen_type.core.mic_glyph import get_glyph

ACCENT = (168, 103, 47)         # #a8672f — large sizes
ACCENT_BRIGHT = (255, 138, 30)  # #ff8a1e — small sizes for taskbar pop
WHITE = (255, 255, 255)

ICO_PATH = ROOT / "src" / "zen_type" / "assets" / "zen-type.ico"
PREVIEW_PATH = ROOT / "build" / "icon_preview.png"
# Includes the standard Windows shell sizes plus intermediates (20/40/96) so
# HiDPI scaling factors (125%/150%) also pick a same-resolution sub-image
# instead of stretching one of the standard sizes.
SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
# Render every sub-image at 8× the target size first, then LANCZOS-downsample
# so the disc and mic edges are properly anti-aliased even at 16/24px.
SUPERSAMPLE = 8


def render_icon(size: int) -> Image.Image:
    if size <= 24:
        ratio, disc = 0.78, ACCENT_BRIGHT
    elif size <= 32:
        ratio, disc = 0.74, ACCENT_BRIGHT
    elif size <= 48:
        ratio, disc = 0.72, ACCENT
    else:
        ratio, disc = 0.66, ACCENT

    big = size * SUPERSAMPLE
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, big - 1, big - 1), fill=disc)

    # Draw mic at supersampled resolution: render the glyph itself even larger
    # and crop to its tight visible bbox so 'mic_h' refers to the real mic.
    raw = get_glyph(WHITE, big)
    bbox = raw.getbbox()
    mic = raw.crop(bbox)
    mic_h = max(8, int(big * ratio))
    mic_w = max(1, int(mic.size[0] * mic_h / mic.size[1]))
    mic = mic.resize((mic_w, mic_h), Image.LANCZOS)
    img.alpha_composite(mic, ((big - mic_w) // 2, (big - mic_h) // 2))

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    imgs = [render_icon(s) for s in SIZES]
    ICO_PATH.parent.mkdir(parents=True, exist_ok=True)
    imgs[0].save(
        ICO_PATH, format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=imgs[1:],
    )
    print(f"[OK] wrote {ICO_PATH}")

    # Preview strip — actual size, no upscaling
    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    total = sum(SIZES) + 6 * (len(SIZES) - 1)
    H = max(SIZES)
    strip = Image.new("RGBA", (total, H), (240, 240, 240, 255))
    x = 0
    for img, s in zip(imgs, SIZES):
        strip.alpha_composite(img, (x, (H - s) // 2))
        x += s + 6
    strip.save(PREVIEW_PATH)
    print(f"[OK] wrote {PREVIEW_PATH}")


if __name__ == "__main__":
    main()
