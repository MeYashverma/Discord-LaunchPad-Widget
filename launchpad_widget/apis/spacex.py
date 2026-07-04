"""SpaceX (r-spacex) provider — secondary data source."""

from __future__ import annotations

import logging
from typing import Any

from ..models import CrewMember, Launch
from ..utils.http_client import HTTPError, HttpClient

logger = logging.getLogger(__name__)


class SpaceXProvider:
    name = "spacex"
    endpoint_upcoming = "https://api.spacexdata.com/v4/launches/upcoming"
    endpoint_rockets = "https://api.spacexdata.com/v4/rockets"
    endpoint_launchpads = "https://api.spacexdata.com/v4/launchpads"
    endpoint_crew = "https://api.spacexdata.com/v4/crew"

    def __init__(self, http: HttpClient) -> None:
        self.http = http
        self._rockets: dict[str, dict[str, Any]] = {}
        self._launchpads: dict[str, dict[str, Any]] = {}
        self._crew: dict[str, dict[str, Any]] = {}

    def next_launches(self, limit: int = 5) -> list[Launch]:
        raw = self.http.get_json(
            self.endpoint_upcoming,
            params={"limit": min(max(limit, 1), 25)},
        )
        if not isinstance(raw, list):
            raise HTTPError(f"Unexpected SpaceX response: {type(raw).__name__}")
        raw_sorted = sorted(raw, key=lambda r: r.get("date_utc") or "")
        return [self._parse(item) for item in raw_sorted[:limit]]

    def _get_rocket(self, rocket_id: str) -> dict[str, Any]:
        if rocket_id in self._rockets:
            return self._rockets[rocket_id]
        try:
            data = self.http.get_json(f"{self.endpoint_rockets}/{rocket_id}")
            if isinstance(data, dict):
                self._rockets[rocket_id] = data
                return data
        except HTTPError as exc:
            logger.debug("Could not fetch SpaceX rocket %s: %s", rocket_id, exc)
        return {}

    def _get_launchpad(self, launchpad_id: str) -> dict[str, Any]:
        if launchpad_id in self._launchpads:
            return self._launchpads[launchpad_id]
        try:
            data = self.http.get_json(f"{self.endpoint_launchpads}/{launchpad_id}")
            if isinstance(data, dict):
                self._launchpads[launchpad_id] = data
                return data
        except HTTPError as exc:
            logger.debug("Could not fetch SpaceX launchpad %s: %s", launchpad_id, exc)
        return {}

    def _get_crew(self, crew_id: str) -> dict[str, Any]:
        if crew_id in self._crew:
            return self._crew[crew_id]
        try:
            data = self.http.get_json(f"{self.endpoint_crew}/{crew_id}")
            if isinstance(data, dict):
                self._crew[crew_id] = data
                return data
        except HTTPError as exc:
            logger.debug("Could not fetch SpaceX crew %s: %s", crew_id, exc)
        return {}

    def _parse(self, item: dict[str, Any]) -> Launch:
        rocket = self._get_rocket(item.get("rocket", ""))
        rocket_name = rocket.get("name", "Unknown Rocket")
        flickr = rocket.get("flickr_images") or []
        rocket_image = flickr[0] if flickr else ""

        launchpad = self._get_launchpad(item.get("launchpad", ""))
        pad_name = launchpad.get("name", "") or launchpad.get("full_name", "")
        locality = launchpad.get("locality", "")
        region = launchpad.get("region", "")
        launch_location = ", ".join(p for p in (locality, region) if p)

        crew: list[CrewMember] = []
        for cid in item.get("crew") or []:
            data = self._get_crew(cid)
            crew.append(
                CrewMember(
                    name=data.get("name", ""),
                    role=data.get("role", ""),
                    agency=data.get("agency", ""),
                    nationality=data.get("nationality", ""),
                )
            )

        patches = item.get("links") or {}
        patch_urls = patches.get("patch") or {}
        mission_patch = patch_urls.get("large") or patch_urls.get("small") or ""
        launch_artwork = (patches.get("flickr") or {}).get("original") or ""
        if not launch_artwork:
            launch_artwork = (patches.get("reddit") or {}).get("campaign") or ""
        launchpad_image = ""

        return Launch(
            source="spacex",
            external_id=item.get("id", ""),
            mission_name=item.get("name", "Unknown Mission"),
            mission_type=", ".join(item.get("payloads") or []) or "",
            mission_description=item.get("details") or "",
            rocket_name=rocket_name,
            rocket_full_name=rocket_name,
            launch_provider="SpaceX",
            crew=crew,
            launch_site=pad_name,
            launch_pad=pad_name,
            launch_location=launch_location,
            country=launchpad.get("country", ""),
            launch_timestamp_utc=item.get("date_utc") or "",
            launch_status=("Go" if not item.get("upcoming") else "TBD"),
            launch_probability=None,
            hold_reason=item.get("holdreason") or "",
            failreason=item.get("failreason") or "",
            is_crewed=bool(crew),
            orbit="",
            destination="",
            rocket_image_url=rocket_image,
            mission_patch_url=mission_patch,
            launch_artwork_url=launch_artwork,
            launchpad_image_url=launchpad_image,
            info_url=(patches.get("webcast") or "") or (patches.get("wikipedia") or ""),
            extra={
                "flight_number": item.get("flight_number"),
            },
        )
