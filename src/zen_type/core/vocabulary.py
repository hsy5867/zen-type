"""Load custom vocabulary from editable txt files under ``refer_doc/``.

File format:
    * One term per line
    * Lines starting with ``#`` are category comments and are skipped
    * Blank lines are skipped

Path resolution:
    * **Development** (running from source): files come from the project root's
      ``refer_doc/`` so edits show up immediately.
    * **Frozen exe** (PyInstaller onefile): on first launch we copy the bundled
      seed files from ``sys._MEIPASS/refer_doc`` into
      ``%APPDATA%/zen-type/refer_doc`` so the user can keep editing them across
      sessions (the temp ``_MEIPASS`` folder is wiped when the exe exits).

Byte-aware packing helper ``pack_terms`` keeps prompts below Groq Whisper's
896-UTF-8-byte limit.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _project_refer_doc() -> Path:
    """Location of ``refer_doc`` in the source checkout."""
    return Path(__file__).resolve().parents[3] / "refer_doc"


def _user_refer_doc() -> Path:
    """Per-user editable copy (used when frozen)."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".config"
    return base / "zen-type" / "refer_doc"


def _bundled_refer_doc() -> Path | None:
    """Inside a PyInstaller onefile bundle, ``sys._MEIPASS`` points at the
    temporary extraction folder that contains ``--add-data`` payloads.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "refer_doc"
    return None


def _seed_user_dir_if_needed(user_dir: Path) -> None:
    """On first launch in a frozen app, copy the bundled seed files into
    ``user_dir`` so the user has something to edit.
    """
    bundled = _bundled_refer_doc()
    if bundled is None or not bundled.exists():
        return
    try:
        user_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("cannot create %s: %s", user_dir, exc)
        return
    for src in bundled.glob("*.txt"):
        dst = user_dir / src.name
        if dst.exists():
            continue
        try:
            shutil.copy2(src, dst)
            logger.info("seeded %s", dst)
        except OSError as exc:
            logger.warning("cannot seed %s: %s", dst, exc)


def _refer_doc_dir() -> Path:
    """Return the active ``refer_doc`` directory depending on run mode."""
    if getattr(sys, "frozen", False):
        user_dir = _user_refer_doc()
        _seed_user_dir_if_needed(user_dir)
        return user_dir
    return _project_refer_doc()


# Resolve once at import time; the directory itself may be edited at runtime.
_REFER_DOC = _refer_doc_dir()

CHINESE_FILE = _REFER_DOC / "常見中文名詞.txt"
ENGLISH_FILE = _REFER_DOC / "常見英文名詞.txt"


def _parse(path: Path) -> list[str]:
    if not path.exists():
        logger.info("vocabulary file missing: %s", path)
        return []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("cannot read %s: %s", path, exc)
        return []

    terms: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        terms.append(stripped)
    return terms


def load_chinese() -> list[str]:
    return _parse(CHINESE_FILE)


def load_english() -> list[str]:
    return _parse(ENGLISH_FILE)


def load_all() -> tuple[list[str], list[str]]:
    """Return (chinese_terms, english_terms)."""
    return load_chinese(), load_english()


def file_paths() -> dict[str, str]:
    return {"chinese": str(CHINESE_FILE), "english": str(ENGLISH_FILE)}


# ---- Byte-aware packing helper ----

def byte_len(s: str) -> int:
    return len(s.encode("utf-8"))


def pack_terms(prefix: str, terms, delim: str, suffix: str, byte_budget: int) -> str:
    """Greedily fit as many terms as possible inside ``byte_budget`` UTF-8 bytes."""
    if not terms or byte_budget <= 0:
        return ""
    overhead = byte_len(prefix) + byte_len(suffix)
    available = byte_budget - overhead
    if available <= 0:
        return ""

    selected: list[str] = []
    used = 0
    for t in terms:
        cost = byte_len(t) + (byte_len(delim) if selected else 0)
        if used + cost > available:
            break
        selected.append(t)
        used += cost
    if not selected:
        return ""
    return prefix + delim.join(selected) + suffix
