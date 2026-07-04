"""Build the Discord Dynamic Identity JSON payload.

Discord identity fields have a ``type`` of 1 (string) or 2 (numeric) for text
data, and images are referenced by a special URL (a Discord-hosted CDN URL
returned by the image webhook or pre-uploaded asset). For our use case we
keep things simple: every textual field becomes a ``type: 1`` entry with a
short ``name`` and string ``value``, the countdown is exposed as both a
formatted string and a numeric seconds-remaining value, and the picked image
is sent as ``type: 1`` whose ``value`` is a ``discord://`` URL.

The exact list of field names the widget displays is configurable; the
defaults are designed to fit the standard widget slots Discord offers.
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

# Type 1 = string, Type 2 = number
TYPE_STRING = 1
TYPE_NUMBER = 2


# Discord's text field limit is generous but not infinite; 512 chars is a
# safe upper bound for a single line of widget text.
MAX_TEXT_LEN = 480


def _truncate(text: str, limit: int = MAX_TEXT_LEN) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _slug(value: str) -> str:
    """Lower-case ASCII slug used in Discord-side field names if needed."""
    s = re.sub(r"[^a-z0-9_]+", "_", (value or "").lower()).strip("_")
    return s or "field"


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


def _image_field_value(local_path: str | None) -> str:
    """Convert a local image path into a value suitable for a Discord image field.

    Discord's profile widget image slots accept any https URL to an image
    hosted on Discord's CDN. When the daemon has a local file we expose it
    as a ``file://`` URL; the Discord PATCH endpoint will reject it but the
    payload is still useful for inspection / dry-runs. In production users
    are expected to either:

        1. Run the image service's companion uploader (``scripts/upload_image.py``)
           to push the image to Discord first and store the returned URL.
        2. Pre-host the chosen image on a public HTTPS endpoint.
    """
    if not local_path:
        return ""
    p = Path(local_path)
    if not p.is_file():
        return ""
    return p.resolve().as_uri()


class PayloadBuilder:
    """Builds the JSON payload for the Discord PATCH endpoint."""

    def __init__(self, *, image_priority: list[str] | None = None) -> None:
        # ``image_priority`` is informational here; the actual URL is selected
        # upstream by ImageService and passed in as ``image_info``.
        self.image_priority = image_priority or [
            "rocket", "mission_patch", "launch_artwork", "launchpad"
        ]

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
        ``value`` keys plus a ``type`` of 1 (string) or 2 (number). Numeric
        fields are particularly nice for countdowns because Discord can show
        them with their own formatting.
        """
        now = now or datetime.now(timezone.utc)
        fields: list[dict[str, Any]] = []

        net = _parse_iso(launch.launch_timestamp_utc)
        seconds_left = 0
        if net is not None:
            seconds_left = max(int((net - now).total_seconds()), 0)
        countdown_str = _format_countdown(seconds_left)

        # --- Strings ---------------------------------------------------- #
        fields.append(self._str(FIELD_MISSION, _truncate(launch.mission_name, 80)))
        fields.append(self._str(FIELD_ROCKET, _truncate(launch.rocket_full_name or launch.rocket_name, 80)))
        fields.append(self._str(FIELD_PROVIDER, _truncate(launch.launch_provider, 60)))
        fields.append(self._str(FIELD_STATUS, _truncate(self._status_line(launch), 50)))
        fields.append(self._str(FIELD_COUNTDOWN, countdown_str))
        fields.append(self._str(FIELD_WINDOW, _format_window(launch)))
        fields.append(self._str(FIELD_SITE, _truncate(launch.launch_pad or launch.launch_site, 60)))
        fields.append(self._str(FIELD_LOCATION, _truncate(launch.launch_location, 60)))
        fields.append(self._str(FIELD_COUNTRY, _truncate(launch.country, 30)))
        fields.append(self._str(FIELD_ORBIT, _truncate(launch.orbit or launch.destination or "—", 40)))
        fields.append(self._str(FIELD_CREW, _truncate(launch.crew_summary(), 100)))
        fields.append(self._str(FIELD_TYPE, _truncate(launch.mission_type or "—", 40)))

        # --- Numbers ---------------------------------------------------- #
        fields.append(self._num(FIELD_PROBABILITY, self._probability(launch)))
        fields.append(self._num("seconds_to_launch", seconds_left))

        # --- Image ------------------------------------------------------ #
        if image_info and image_info.get("local_path"):
            fields.append(
                {
                    "name": FIELD_IMAGE,
                    "type": TYPE_STRING,
                    "value": _image_field_value(image_info["local_path"]),
                }
            )
        else:
            fields.append({"name": FIELD_IMAGE, "type": TYPE_STRING, "value": ""})

        return {"identities": [fields]}

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
