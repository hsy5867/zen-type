"""Shared file-logging helper for parent (tray app) and child (settings window).

Both processes call ``attach_file_logger`` early in ``main()`` so that any
exception — including silent failures from PyInstaller --noconsole frozen
exes — gets persisted to ``%APPDATA%\\zen-type\\zen-type.log`` (Windows) or
``~/.config/zen-type/zen-type.log`` (Unix).

The same log file is also handed to ``subprocess.Popen`` as the child's
stdout/stderr (see ``app.py:_open_settings_window``) so that pre-Python
crashes (PyInstaller bootloader, missing DLLs) still leave a trace.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from zen_type.config.settings import get_config_dir

LOG_FILENAME = "zen-type.log"


def get_log_path() -> Path:
    return get_config_dir() / LOG_FILENAME


def attach_file_logger(role: str, *, debug: bool = False) -> Path:
    """Attach a rotating file handler to the root logger.

    ``role`` is a short tag like ``"parent"`` or ``"settings-child"`` that gets
    embedded in every record so we can tell the two processes apart when both
    write to the same file.

    Returns the resolved log path so the caller can pass it to subprocess.Popen
    as a raw fd target.
    """
    log_path = get_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    # Avoid duplicate handlers if attach_file_logger is called twice.
    for h in list(root.handlers):
        if getattr(h, "_zen_type_file_handler", False):
            return log_path

    handler = RotatingFileHandler(
        log_path,
        maxBytes=512 * 1024,
        backupCount=2,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG if debug else logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            f"%(asctime)s [{role}] %(levelname)-7s %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler._zen_type_file_handler = True  # type: ignore[attr-defined]
    root.addHandler(handler)

    # Best-effort startup line so it's obvious in the log when each process
    # boots, even if it later crashes silently.
    logging.getLogger(__name__).info(
        "log attached: role=%s frozen=%s argv=%s",
        role,
        getattr(sys, "frozen", False),
        sys.argv,
    )
    return log_path
