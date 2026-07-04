"""Provider interface."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from ..models import Launch

logger = logging.getLogger(__name__)


@runtime_checkable
class LaunchProvider(Protocol):
    """Abstract interface every launch-data source implements."""

    name: str

    def next_launches(self, limit: int = 5) -> list[Launch]:
        """Return the next ``limit`` upcoming launches, ordered by time."""
        ...

    def next_launch(self) -> Launch | None:
        """Return the single next upcoming launch (or None on failure)."""
        try:
            results = self.next_launches(1)
            return results[0] if results else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] next_launch failed: %s", self.name, exc)
            return None
