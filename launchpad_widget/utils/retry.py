"""Tiny retry helper."""

from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

import requests

logger = logging.getLogger(__name__)

T = TypeVar("T")


def call_with_retries(
    func: Callable[[], T],
    *,
    attempts: int = 3,
    backoff_factor: float = 1.5,
    retry_on: tuple[type[BaseException], ...] = (requests.RequestException, TimeoutError),
    label: str = "operation",
) -> T:
    if attempts < 1:
        attempts = 1
    last_exc: BaseException | None = None
    for i in range(1, attempts + 1):
        try:
            return func()
        except retry_on as exc:
            last_exc = exc
            wait = backoff_factor ** (i - 1)
            logger.warning(
                "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                label, i, attempts, exc, wait,
            )
            if i < attempts:
                time.sleep(wait)
    assert last_exc is not None
    raise last_exc
