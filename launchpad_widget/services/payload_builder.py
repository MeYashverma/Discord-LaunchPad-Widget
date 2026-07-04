"""Build the Discord Dynamic Identity JSON payload.

Discord identity fields have a ``type`` of:

    1 = string (text)
    2 = number
    3 = image (nested ``value.url``)

The exact list of field names the widget displays is configured to match
the Data Fields in the Discord widget editor.  Keep this list in sync with
``docs/FIELDS.md``.

Reference (PATCH endpoint body shape):

    PATCH /applications/{APP_ID}/users/{USER_ID}/identities/0/profile
    Body: {"identities": [[ {"name": "...", "type": 1|2|3, "value": ...}, ... ]]}
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models import Launch

logger = logging.getLogger(__name__)


# Field name constants — these MUST match the Data Field names configured
# in the Discord widget editor.  Keep them short, Discord truncates long
# values.
FIELD_MISSION = "mission"
FIELD_ROCKET = "rocket"
FIELD_PROVIDER = "provider"
FIELD_STATUS = "status"
FIELD_COUNTDOWN = "countdown"
FIELD_WINDOW = "window"
FIELD_SITE = "site"
FIELD_LOCATION = "location"
FIELD_COUNTRY = "country"
FIELD_ORBIT = "orbit"
FIELD_CREW = "crew"
FIELD_TYPE = "type"
FIELD_PROBABILITY = "probability"
FIELD_IMAGE = "image"

# Discord dynamic-identity type codes
TYPE_STRING = 1
TYPE_NUMBER = 2
TYPE_IMAGE = 3


# Discord's text field limit is generous but not infinite; 512 chars is a
# safe upper bound for a single line of widget text.
MAX_TEXT_LEN = 480


# The set of fields the widget editor defines.  The daemon always sends
# exactly these (in this order) so that Discord binds every slot.
DEFAULT_FIELD_ORDER: list[str] = [
    FIELD_MISSION,
    FIELD_ROCKET,
    FIELD_PROVIDER,
    FIELD_STATUS,
    FIELD_COUNTDOWN,
    FIELD_WINDOW,
    FIELD_SITE,
    FIELD_LOCATION,
    FIELD_COUNTRY,
    FIELD_ORBIT,
    FIELD_CREW,
    FIELD_TYPE,
    FIELD_PROBABILITY,
    FIELD_IMAGE,
]


def _truncate(text: str, limit: int = MAX_TEXT_LEN) -> str:
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
        # 'Z' suffix is not understood by fromisoformat in <3.11
        cleaned = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _format_countdown(seconds: int) -> str:
    """Format a non-negative number of seconds as ``Dd HH:MM:SS``."""
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
            pretty += " → " + e.astimezone(timezone.utc).strftime("%H:%M UTC")
    return _truncate(pretty, 80)


class PayloadBuilder:
    """Builds the JSON payload for the Discord PATCH endpoint."""

    def __init__(
        self,
        *,
        image_priority: list[str] | None = None,
        field_order: list[str] | None = None,
    ) -> None:
        self.image_priority = image_priority or [
            "rocket", "mission_patch", "launch_artwork", "launchpad"
        ]
        # Override the default field set if the user wants a subset.
        self.field_order = field_order or list(DEFAULT_FIELD_ORDER)

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
        """Return the ``identities`` payload to send to Discord.

        Discord's PATCH endpoint expects the body to be ``{"identities": [...]}``,
        where each identity is a list of field dicts with ``name`` and
        ``value`` keys plus a ``type`` of 1 (string), 2 (number) or 3 (image).
        """
        now = now or datetime.now(timezone.utc)
        all_fields: dict[str, dict[str, Any]] = {}

        net = _parse_iso(launch.launch_timestamp_utc)
        seconds_left = 0
        if net is not None:
            seconds_left = max(int((net - now).total_seconds()), 0)
        countdown_str = _format_countdown(seconds_left)

        # --- Build every field up-front so order is deterministic --- #
        all_fields[FIELD_MISSION] = self._str(
            FIELD_MISSION, _truncate(launch.mission_name, 80)
        )
        all_fields[FIELD_ROCKET] = self._str(
            FIELD_ROCKET, _truncate(launch.rocket_full_name or launch.rocket_name, 80)
        )
        all_fields[FIELD_PROVIDER] = self._str(
            FIELD_PROVIDER, _truncate(launch.launch_provider, 60)
        )
        all_fields[FIELD_STATUS] = self._str(
            FIELD_STATUS, _truncate(self._status_line(launch), 50)
        )
        all_fields[FIELD_COUNTDOWN] = self._str(FIELD_COUNTDOWN, countdown_str)
        all_fields[FIELD_WINDOW] = self._str(FIELD_WINDOW, _format_window(launch))
        all_fields[FIELD_SITE] = self._str(
            FIELD_SITE, _truncate(launch.launch_pad or launch.launch_site, 60)
        )
        all_fields[FIELD_LOCATION] = self._str(
            FIELD_LOCATION, _truncate(launch.launch_location, 60)
        )
        all_fields[FIELD_COUNTRY] = self._str(
            FIELD_COUNTRY, _truncate(launch.country, 30)
        )
        all_fields[FIELD_ORBIT] = self._str(
            FIELD_ORBIT, _truncate(launch.orbit or launch.destination or "—", 40)
        )
        all_fields[FIELD_CREW] = self._str(
            FIELD_CREW, _truncate(launch.crew_summary(), 100)
        )
        all_fields[FIELD_TYPE] = self._str(
            FIELD_TYPE, _truncate(launch.mission_type or "—", 40)
        )
        all_fields[FIELD_PROBABILITY] = self._num(
            FIELD_PROBABILITY, self._probability(launch)
        )
        all_fields[FIELD_IMAGE] = self._image_field(image_info)

        # Honour the configured field order; ignore unknowns so adding a
        # field in the editor without a matching constant doesn't break us.
        ordered: list[dict[str, Any]] = []
        for name in self.field_order:
            if name in all_fields:
                ordered.append(all_fields[name])

        return {"identities": [ordered]}

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
    def _image_field(image_info: dict[str, Any] | None) -> dict[str, Any]:
        """Build a ``type: 3`` image field.

        Order of preference:
            1. ``image_info["cdn_url"]``  — a Discord-hosted https URL
            2. ``image_info["https_url"]`` — any other https URL
            3. empty string (no image)
        """
        url = ""
        if image_info:
            url = (
                image_info.get("cdn_url")
                or image_info.get("https_url")
                or ""
            )
            # Discord requires https:// for image fields
            if url and not url.lower().startswith("https://"):
                url = ""
        return {
            "name": FIELD_IMAGE,
            "type": TYPE_IMAGE,
            "value": {"url": url},
        }

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
