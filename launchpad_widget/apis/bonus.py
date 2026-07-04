"""Optional / bonus data sources.

These don't drive the widget on their own — they enrich ``Launch.extra``
with extra context (e.g. a brief APOD blurb, the ISS position for fun).
"""

from __future__ import annotations

import logging
from typing import Any

from ..utils.http_client import HttpClient

logger = logging.getLogger(__name__)


class Nasardoesnt:
    """Tiny client for a few NASA endpoints that don't need an API key."""

    def __init__(self, http: HttpClient, api_key: str = "DEMO_KEY") -> None:
        self.http = http
        self.api_key = api_key

    def apod_blurb(self) -> dict[str, Any] | None:
        """Return a tiny APOD summary, or None on failure."""
        try:
            data = self.http.get_json(
                "https://api.nasa.gov/planetary/apod",
                params={"api_key": self.api_key, "thumbs": True},
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("APOD fetch failed: %s", exc)
            return None
        if not isinstance(data, dict):
            return None
        return {
            "title": data.get("title", ""),
            "date": data.get("date", ""),
            "url": data.get("url") or data.get("thumbnail_url", ""),
            "explanation": (data.get("explanation") or "")[:240],
        }


class WhereTheIssAt:
    """Client for https://wheretheiss.at — gives the current ISS position."""

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def position(self) -> dict[str, Any] | None:
        try:
            data = self.http.get_json("https://api.wheretheiss.at/v1/satellites/25544")
        except Exception as exc:  # noqa: BLE001
            logger.debug("ISS position fetch failed: %s", exc)
            return None
        if not isinstance(data, dict):
            return None
        return {
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "altitude_km": data.get("altitude"),
            "velocity_kph": data.get("velocity"),
        }
