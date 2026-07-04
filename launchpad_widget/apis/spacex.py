"""SpaceX (r-spacex/SpaceX-API, v4) provider.

Used as a fallback for SpaceX-specific launches, and as a redundant data
source for when LL2 is rate-limited. The API is fully open and unauthenticated.

Endpoint used:
    GET https://api.spacexdata.com/v4/launches/upcoming
"""

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

    def __init__(self, http: HttpClient) -> None:
        self.http = http
        self._rockets: dict[str, dict[str, Any]] = {}
        self._launchpads: dict[str, dict[str, Any]] = {}
        self._crew_lookup: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def next_launches(self, limit: int = 5) -> list[Launch]:
        raw = self.http.get_json(
            self.endpoint_upcoming,
            params={"limit": min(max(limit, 1), 25)},
        )
        if not isinstance(raw, list):
            raise HTTPError(f"Unexpected SpaceX response: {type(raw).__name__}")
        # SpaceX returns launches in descending date order; reverse for ascending
        raw_sorted = sorted(raw, key=lambda r: r.get("date_utc") or "")
        return [self._parse(item) for item in raw_sorted[:limit]]

    # ------------------------------------------------------------------ #
    # Lazy lookups                                                        #
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Parsing                                                             #
    # ------------------------------------------------------------------ #

    def _parse(self, item: dict[str, Any]) -> Launch:
        rocket = self._get_rocket(item.get("rocket", ""))
        rocket_name = rocket.get("name", "Unknown Rocket")
        # The SpaceX v4 rocket object includes an array of flickr_images plus
        # a wikipedia image — we prefer the first flickr one.
        rocket_image = ""
        flickr = rocket.get("flickr_images") or []
        if flickr:
            rocket_image = flickr[0]
        else:
            rocket_image = ""

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

        # Mission patch from SpaceX is on the launch payload
        patches = item.get("links") or {}
        patch_urls = patches.get("patch") or {}
        mission_patch = patch_urls.get("large") or patch_urls.get("small") or ""
        # Other images
        launch_artwork = (patches.get("reddit") or {}).get("campaign") or ""
        if not launch_artwork:
            launch_artwork = (patches.get("flickr") or {}).get("original") or ""
        # No native launchpad image from the v4 API; use wikipedia
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
                "static_fire_date_utc": item.get("static_fire_date_utc"),
                "tbd": item.get("tbd"),
                "net_precision": item.get("net_precision"),
            },
        )

    def _get_crew(self, crew_id: str) -> dict[str, Any]:
        if crew_id in self._crew_lookup:
            return self._crew_lookup[crew_id]
        try:
            data = self.http.get_json(f"https://api.spacexdata.com/v4/crew/{crew_id}")
            if isinstance(data, dict):
                self._crew_lookup[crew_id] = data
                return data
        except HTTPError as exc:
            logger.debug("Could not fetch SpaceX crew %s: %s", crew_id, exc)
        return {}
