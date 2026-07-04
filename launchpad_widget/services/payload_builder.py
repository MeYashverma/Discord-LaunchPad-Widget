"""Build the Discord Dynamic Identity JSON payload.

The Discord profile widget has TWO independent sections, addressed by two
separate entries in the ``identities`` array:

    identities[0]  -> Widget TOP    (Image, Title, Subtitle 1..3)
    identities[1]  -> Widget BOTTOM (the list of stat fields)

Each entry is an array of fields::

    {"name": "<editor field name>", "type": 1|2|3, "value": ...}

Where:
    type 1 = text    -> value is a string
    type 2 = number  -> value is a number
    type 3 = image   -> value is {"url": "https://..."}

The names must match the Data Field names in the Discord widget editor
EXACTLY (case-sensitive, including spaces and capitalisation).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..models import Launch

logger = logging.getLogger(__name__)


# --- Widget TOP field names (must match editor exactly) --- #
TOP_IMAGE = "Image"            # type 3
TOP_TITLE = "Title"            # type 1
TOP_SUBTITLE_1 = "Subtitle 1"  # type 1
TOP_SUBTITLE_2 = "Subtitle 2"  # type 1
TOP_SUBTITLE_3 = "Subtitle 3"  # type 1

# --- Widget BOTTOM field names (must match editor exactly) --- #
BOTTOM_MISSION = "mission"
BOTTOM_ROCKET = "rocket"
BOTTOM_PROVIDER = "provider"
BOTTOM_STATUS = "status"
BOTTOM_COUNTDOWN = "countdown"
BOTTOM_WINDOW = "window"
BOTTOM_SITE = "site"
BOTTOM_LOCATION = "location"
BOTTOM_COUNTRY = "country"
BOTTOM_ORBIT = "orbit"
BOTTOM_CREW = "crew"
BOTTOM_TYPE = "type"
BOTTOM_PROBABILITY = "probability"
BOTTOM_IMAGE = "image"

# Discord dynamic-identity type codes
TYPE_STRING = 1
TYPE_NUMBER = 2
TYPE_IMAGE = 3


MAX_TEXT_LEN = 480


def _truncate(text: Any, limit: int = MAX_TEXT_LEN) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        cleaned = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _format_countdown(seconds: int) -> str:
    """``T-Dd HH:MM:SS`` or ``T-HH:MM:SS``."""
    if seconds < 0:
        seconds = 0
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days > 0:
        return f"T-{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"T-{hours:02d}:{minutes:02d}:{secs:02d}"


def _format_window(launch: Launch) -> str:
    start = (launch.extra or {}).get("window_start") or launch.launch_timestamp_utc
    end = (launch.extra or {}).get("window_end")
    if not start:
        return "TBD"
    s = _parse_iso(start)
    if not s:
        return _truncate(start, 40)
    pretty = s.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if end:
        e = _parse_iso(end)
        if e:
            pretty += " \u2192 " + e.astimezone(timezone.utc).strftime("%H:%M UTC")
    return _truncate(pretty, 80)


def _image_url(image_info: dict[str, Any] | None) -> str:
    """Best Discord-CDN URL for the image field, or ''."""
    if not image_info:
        return ""
    url = (
        image_info.get("cdn_url")
        or image_info.get("https_url")
        or ""
    )
    if url and not url.lower().startswith("https://"):
        return ""
    return url


class PayloadBuilder:
    """Builds the JSON payload for the Discord PATCH endpoint."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def build(
        self,
        launch: Launch,
        *,
        image_info: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Return ``{"identities": [top_fields, bottom_fields]}``."""
        now = now or datetime.now(timezone.utc)

        net = _parse_iso(launch.launch_timestamp_utc)
        seconds_left = 0
        if net is not None:
            seconds_left = max(int((net - now).total_seconds()), 0)
        countdown_str = _format_countdown(seconds_left)

        top = self._build_top(launch, image_info, countdown_str)
        bottom = self._build_bottom(launch, countdown_str, image_info)
        return {"identities": [top, bottom]}

    # ------------------------------------------------------------------ #
    # Top (Image / Title / Subtitle 1-3)                                  #
    # ------------------------------------------------------------------ #

    def _build_top(
        self,
        launch: Launch,
        image_info: dict[str, Any] | None,
        countdown_str: str,
    ) -> list[dict[str, Any]]:
        rocket = launch.rocket_full_name or launch.rocket_name or "Unknown Rocket"
        provider = launch.launch_provider or "Unknown Provider"
        site = launch.launch_pad or launch.launch_site or "Unknown Site"
        location = launch.launch_location or ""

        sub1 = f"{rocket} \u00b7 {provider}"
        sub2 = countdown_str
        sub3 = site + (f" \u00b7 {location}" if location else "")

        return [
            {
                "name": TOP_IMAGE,
                "type": TYPE_IMAGE,
                "value": {"url": _image_url(image_info)},
            },
            {
                "name": TOP_TITLE,
                "type": TYPE_STRING,
                "value": _truncate(launch.mission_name or "Unknown Mission", 80),
            },
            {
                "name": TOP_SUBTITLE_1,
                "type": TYPE_STRING,
                "value": _truncate(sub1, 100),
            },
            {
                "name": TOP_SUBTITLE_2,
                "type": TYPE_STRING,
                "value": _truncate(sub2, 50),
            },
            {
                "name": TOP_SUBTITLE_3,
                "type": TYPE_STRING,
                "value": _truncate(sub3, 100),
            },
        ]

    # ------------------------------------------------------------------ #
    # Bottom (stat fields)                                                #
    # ------------------------------------------------------------------ #

    def _build_bottom(
        self,
        launch: Launch,
        countdown_str: str,
        image_info: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        return [
            self._str(BOTTOM_MISSION, _truncate(launch.mission_name, 80)),
            self._str(BOTTOM_ROCKET, _truncate(launch.rocket_full_name or launch.rocket_name, 80)),
            self._str(BOTTOM_PROVIDER, _truncate(launch.launch_provider, 60)),
            self._str(BOTTOM_STATUS, _truncate(self._status_line(launch), 50)),
            self._str(BOTTOM_COUNTDOWN, countdown_str),
            self._str(BOTTOM_WINDOW, _format_window(launch)),
            self._str(BOTTOM_SITE, _truncate(launch.launch_pad or launch.launch_site, 60)),
            self._str(BOTTOM_LOCATION, _truncate(launch.launch_location, 60)),
            self._str(BOTTOM_COUNTRY, _truncate(launch.country, 30)),
            self._str(BOTTOM_ORBIT, _truncate(launch.orbit or launch.destination or "\u2014", 40)),
            self._str(BOTTOM_CREW, _truncate(launch.crew_summary(), 100)),
            self._str(BOTTOM_TYPE, _truncate(launch.mission_type or "\u2014", 40)),
            self._num(BOTTOM_PROBABILITY, self._probability(launch)),
            {
                "name": BOTTOM_IMAGE,
                "type": TYPE_IMAGE,
                "value": {"url": _image_url(image_info)},
            },
        ]

    # ------------------------------------------------------------------ #
    # Field helpers                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _str(name: str, value: str) -> dict[str, Any]:
        return {"name": name, "type": TYPE_STRING, "value": value}

    @staticmethod
    def _num(name: str, value: int | float | None) -> dict[str, Any]:
        if value is None:
            value = 0
        return {"name": name, "type": TYPE_NUMBER, "value": int(value)}

    @staticmethod
    def _status_line(launch: Launch) -> str:
        if launch.failreason:
            return "Scrubbed"
        if launch.hold_reason:
            return f"Hold: {launch.hold_reason[:30]}"
        if launch.launch_status:
            return launch.launch_status
        return "Scheduled"

    @staticmethod
    def _probability(launch: Launch) -> int | None:
        if launch.launch_probability is None:
            return None
        try:
            return int(launch.launch_probability)
        except (TypeError, ValueError):
            return None
