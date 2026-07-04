"""Data models used across the widget.

We keep this module deliberately small: a single ``Launch`` dataclass
captures everything the widget wants to display, regardless of which API the
raw data originally came from. The API modules are responsible for mapping
their own payloads onto this shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class CrewMember:
    name: str
    role: str = ""
    agency: str = ""
    nationality: str = ""

    def to_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class Launch:
    """A normalized launch record."""

    # Identity
    source: str = ""               # "launch_library" or "spacex"
    external_id: str = ""          # upstream id
    mission_name: str = "Unknown Mission"
    mission_type: str = ""
    mission_description: str = ""

    # Vehicle
    rocket_name: str = "Unknown Rocket"
    rocket_full_name: str = ""
    launch_provider: str = "Unknown Provider"
    crew: list[CrewMember] = field(default_factory=list)

    # Location
    launch_site: str = ""
    launch_pad: str = ""
    launch_location: str = ""
    country: str = ""

    # Timing & status
    launch_timestamp_utc: str = ""  # ISO-8601 string
    launch_status: str = ""         # "Go", "TBD", "Hold", "Success", etc.
    launch_probability: int | None = None
    hold_reason: str = ""
    failreason: str = ""
    is_crewed: bool = False

    # Orbit
    orbit: str = ""
    destination: str = ""

    # Media (raw URLs; the image service picks the best one)
    rocket_image_url: str = ""
    mission_patch_url: str = ""
    launch_artwork_url: str = ""
    launchpad_image_url: str = ""
    info_url: str = ""

    # Free-form additional metadata, also passed through to the widget
    extra: dict[str, Any] = field(default_factory=dict)

    def primary_image_url(self, priority: list[str]) -> str:
        """Return the best available image URL given the configured priority.

        ``priority`` is an ordered list of attribute names. The first one that
        yields a non-empty string wins.
        """
        for attr in priority:
            value = getattr(self, attr, "")
            if value:
                return value
        return ""

    def crew_summary(self, limit: int = 4) -> str:
        """Short, human-friendly crew summary for the widget text fields."""
        if not self.crew:
            return "Uncrewed"
        names = [c.name for c in self.crew if c.name]
        if not names:
            return "Uncrewed"
        if len(names) <= limit:
            return ", ".join(names)
        return ", ".join(names[:limit]) + f" +{len(names) - limit}"

    def to_dict(self) -> dict[str, Any]:
        """Recursively serialise for caching."""
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Launch":
        crew_data = data.pop("crew", []) or []
        crew = [CrewMember(**c) for c in crew_data]
        return cls(crew=crew, **data)
