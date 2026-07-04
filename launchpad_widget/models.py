"""Data models."""

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
    source: str = ""
    external_id: str = ""
    mission_name: str = "Unknown Mission"
    mission_type: str = ""
    mission_description: str = ""

    rocket_name: str = "Unknown Rocket"
    rocket_full_name: str = ""
    launch_provider: str = "Unknown Provider"
    crew: list[CrewMember] = field(default_factory=list)

    launch_site: str = ""
    launch_pad: str = ""
    launch_location: str = ""
    country: str = ""

    launch_timestamp_utc: str = ""
    launch_status: str = ""
    launch_probability: int | None = None
    hold_reason: str = ""
    failreason: str = ""
    is_crewed: bool = False

    orbit: str = ""
    destination: str = ""

    rocket_image_url: str = ""
    mission_patch_url: str = ""
    launch_artwork_url: str = ""
    launchpad_image_url: str = ""
    info_url: str = ""

    extra: dict[str, Any] = field(default_factory=dict)

    def primary_image_url(self, priority: list[str]) -> str:
        for attr in priority:
            value = getattr(self, attr, "")
            if value:
                return value
        return ""

    def crew_summary(self, limit: int = 4) -> str:
        if not self.crew:
            return "Uncrewed"
        names = [c.name for c in self.crew if c.name]
        if not names:
            return "Uncrewed"
        if len(names) <= limit:
            return ", ".join(names)
        return ", ".join(names[:limit]) + f" +{len(names) - limit}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Launch":
        crew_data = data.pop("crew", []) or []
        crew = [CrewMember(**c) for c in crew_data]
        return cls(crew=crew, **data)
