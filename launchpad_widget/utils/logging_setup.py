"""Logging helpers."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def configure_logging(log_file: str, level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("launchpad_widget")
    logger.setLevel(getattr(logging, level, logging.INFO))
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        log_dir = os.path.dirname(os.path.abspath(log_file))
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        fh = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as exc:
        sys.stderr.write(f"warning: could not attach file logger: {exc}\n")

    if getattr(sys, "stdout", None) is not None:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    return logger
