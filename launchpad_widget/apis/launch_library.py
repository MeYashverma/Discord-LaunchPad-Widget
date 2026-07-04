"""Launch Library 2 (TheSpaceDevs) provider.

This is the primary data source because it covers every launch operator
worldwide, not just SpaceX. The free tier allows 15 requests/hour which is
plenty for our use case (we cache aggressively).

API documentation:
    https://ll.thespacedevs.com/docs
Endpoint used:
    GET https://ll.thespacedevs.com/2.3.0/launches/upcoming/
"""

from __future__ import annotations

import logging
from typing import Any

from ..models import CrewMember, Launch
from ..utils.http_client import HTTPError, HttpClient

logger = logging.getLogger(__name__)


class LaunchLibrary2Provider:
    name = "launch_library"
    endpoint = "https://ll.thespacedevs.com/2.3.0/launches/upcoming/"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def next_launches(self, limit: int = 5) -> list[Launch]:
        params = {
            "limit": min(max(limit, 1), 25),
            "mode": "detailed",
            "ordering": "net",  # ascending by NET (No Earlier Than)
        }
        data = self.http.get_json(self.endpoint, params=params)
        if not isinstance(data, dict):
            raise HTTPError(f"Unexpected LL2 response shape: {type(data).__name__}")
        results = data.get("results") or []
        launches: list[Launch] = []
        for item in results:
            try:
                launches.append(self._parse(item))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping malformed LL2 launch: %s", exc)
        return launches

    # ------------------------------------------------------------------ #
    # Parsing helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse(item: dict[str, Any]) -> Launch:
        rocket_cfg = item.get("rocket") or {}
        configuration = rocket_cfg.get("configuration") or {}
        launcher_conf = item.get("launcher_config") or {}
        # "full_name" lives on the rocket configuration object
        rocket_full = (
            configuration.get("full_name")
            or launcher_conf.get("full_name")
            or configuration.get("name")
            or "Unknown Rocket"
        )
        rocket_short = configuration.get("name") or rocket_full

        lsp = item.get("launch_service_provider") or {}
        provider_name = lsp.get("name") or "Unknown Provider"

        pad = item.get("pad") or {}
        location = pad.get("location") or {}
        pad_name = pad.get("name") or ""
        location_name = location.get("name") or ""
        # ``pad.country`` on LL2 is always a structured object (id, name,
        # alpha_2_code, alpha_3_code). ``location.country_code`` is the
        # 2-letter ISO code as a fallback.
        raw_country = pad.get("country")
        if isinstance(raw_country, dict):
            country = (
                raw_country.get("name")
                or raw_country.get("alpha_2_code")
                or raw_country.get("alpha_3_code")
                or ""
            )
        elif isinstance(raw_country, str):
            country = raw_country
        else:
            country = ""
        if not country:
            country = location.get("country_code") or ""

        mission = item.get("mission") or {}
        mission_type = ""
        if mission.get("type"):
            mission_type = mission["type"]
        mission_desc = mission.get("description") or ""

        status = item.get("status") or {}
        status_name = status.get("name") or ""
        status_id = status.get("id")
        probability = item.get("probability")
        hold_reason = item.get("holdreason") or ""
        failreason = item.get("failreason") or ""

        # Image preferences (priority order, decided later by the service):
        # 1. configuration.image_url (rocket artwork)
        # 2. mission.image (mission patch)
        # 3. image (LL2's primary launch image)
        rocket_image = configuration.get("image_url") or ""
        mission_patch = (mission.get("image") or {}).get("image_url") or ""
        launch_artwork = item.get("image") or ""
        launchpad_image = (pad.get("image_url") or "")

        # Crew
        crew: list[CrewMember] = []
        for entry in item.get("crew") or []:
            person = entry.get("astronaut") or {}
            crew.append(
                CrewMember(
                    name=person.get("name", ""),
                    role=entry.get("role", "") or entry.get("role_en", ""),
                    agency=(person.get("agency") or {}).get("name", ""),
                    nationality=person.get("nationality", ""),
                )
            )

        # Orbit
        orbit = ""
        if mission.get("orbit"):
            orbit = mission["orbit"].get("name", "") or ""
        destination = ""
        if mission.get("orbit"):
            destination = (mission["orbit"].get("abbrev") or "")

        return Launch(
            source="launch_library",
            external_id=str(item.get("id", "")),
            mission_name=item.get("name") or "Unknown Mission",
            mission_type=mission_type,
            mission_description=mission_desc,
            rocket_name=rocket_short,
            rocket_full_name=rocket_full,
            launch_provider=provider_name,
            crew=crew,
            launch_site=location_name,
            launch_pad=pad_name,
            launch_location=location_name,
            country=country,
            launch_timestamp_utc=item.get("net") or "",
            launch_status=status_name or str(status_id or ""),
            launch_probability=int(probability) if probability is not None else None,
            hold_reason=hold_reason,
            failreason=failreason,
            is_crewed=bool(crew),
            orbit=orbit,
            destination=destination,
            rocket_image_url=rocket_image,
            mission_patch_url=mission_patch,
            launch_artwork_url=launch_artwork,
            launchpad_image_url=launchpad_image,
            info_url=(item.get("info_urls") or [{}])[0].get("url", "") if item.get("info_urls") else "",
            extra={
                "ll2_status_id": status_id,
                "window_start": item.get("window_start"),
                "window_end": item.get("window_end"),
            },
        )
