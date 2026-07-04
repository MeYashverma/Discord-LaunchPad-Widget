"""Provider interface."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from ..models import Launch

logger = logging.getLogger(__name__)


@runtime_checkable
class LaunchProvider(Protocol):
    name: str

    def next_launches(self, limit: int = 5) -> list[Launch]:
        ...

    def next_launch(self) -> Launch | None:
        try:
            results = self.next_launches(1)
            return results[0] if results else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] next_launch failed: %s", self.name, exc)
            return None
