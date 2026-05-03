"""zen-type — AI voice input tool."""

__version__ = "2.0.8"
__release_notes__ = (
    "2.0.8  — exe icon rendered at 8× supersample then LANCZOS-downsampled "
    "to each target size, so the disc edge and mic glyph have proper "
    "anti-aliasing at 16/24/32px. Added intermediate sub-images (20/40/96) "
    "so HiDPI scaling factors (125%/150%) pick a native-resolution match "
    "instead of stretching the next standard size."
)
