"""Generate tray icons on the fly with Pillow.

Flat design: a single coloured disc filling the frame plus the mic glyph
loaded VERBATIM from the bundled reference PNG
(``zen_type/assets/mic_reference.png``). No border, no ring, no shadow.

For IDLE the disc is light gray (#D0D0D0) and the mic is dark gray (#555555)
so the silhouette stays visible without contrast issues.
"""

from __future__ import annotations

from zen_type.core.constants import PipelineState
from zen_type.core.mic_glyph import paste_mic

# Disc colour per state (saturated, flat)
_STATE_COLORS = {
    PipelineState.IDLE:         (208, 208, 208),  # #D0D0D0
    PipelineState.RECORDING:    (220,  53,  69),  # #DC3545
    PipelineState.TRANSCRIBING: (255, 152,   0),  # #FF9800
    PipelineState.POLISHING:    ( 33, 150, 243),  # #2196F3
    PipelineState.INJECTING:    ( 76, 175,  80),  # #4CAF50
    PipelineState.ERROR:        (138, 138, 138),  # #8A8A8A
}

# Mic colour per state — white on saturated discs, dark gray on light IDLE disc
_MIC_DARK = (85, 85, 85)
_MIC_WHITE = (255, 255, 255)
_GLYPH_COLORS = {
    PipelineState.IDLE:         _MIC_DARK,
    PipelineState.RECORDING:    _MIC_WHITE,
    PipelineState.TRANSCRIBING: _MIC_WHITE,
    PipelineState.POLISHING:    _MIC_WHITE,
    PipelineState.INJECTING:    _MIC_WHITE,
    PipelineState.ERROR:        _MIC_WHITE,
}


def create_tray_icon(
    state: PipelineState = PipelineState.IDLE,
    size: int = 64,
    levels: list[float] | None = None,  # accepted for API compat; unused
):
    """Return a Pillow RGBA Image: full-bleed coloured disc + bundled mic glyph."""
    from PIL import Image, ImageDraw

    color = _STATE_COLORS.get(state, _STATE_COLORS[PipelineState.IDLE])
    glyph_color = _GLYPH_COLORS.get(state, _MIC_DARK)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Single solid disc filling the frame
    draw.ellipse((0, 0, size - 1, size - 1), fill=color)
    # Mic glyph from reference image — height ≈ 65% of disc diameter
    paste_mic(img, size // 2, size // 2, int(size * 0.65), glyph_color)
    return img
