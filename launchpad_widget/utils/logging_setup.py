"""Logging helpers.

A rotating file handler is always attached so that the daemon is diagnosable
when run in the background or inside GitHub Actions. A console handler is
added only when a real stdout exists (so pythonw.exe / detached runners don't
crash on ``print()``).
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def configure_logging(log_file: str, level: str = "INFO") -> logging.Logger:
    """Configure and return the package-wide logger.

    Calling this more than once is safe: the underlying logger is reused and
    duplicate handlers are removed first.
    """
    logger = logging.getLogger("launchpad_widget")
    logger.setLevel(getattr(logging, level, logging.INFO))
    logger.propagate = False

    # Remove any handlers that may have been attached by a previous call
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    # File handler (always; safe under pythonw)
    try:
        log_dir = os.path.dirname(os.path.abspath(log_file))
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        fh = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as exc:
        # Read-only filesystem / no permission: just fall back to console
        sys.stderr.write(f"warning: could not attach file logger: {exc}\n")

    # Console handler (only when a tty / pipe is attached)
    if getattr(sys, "stdout", None) is not None:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    return logger
