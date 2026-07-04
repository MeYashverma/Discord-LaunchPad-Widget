"""Image service: download, cache, and pick the best image for a launch.

The priority list is configurable but defaults to the order recommended in
the spec:

    1. Rocket image
    2. Mission patch
    3. Launch artwork
    4. Launchpad image

If none of those are available we fall back to a bundled PNG.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any

from ..models import Launch
from ..utils.cache import ImageCache
from ..utils.http_client import HTTPError, HttpClient

logger = logging.getLogger(__name__)


# Discord profile image constraints (dynamic identity images)
MAX_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _safe_filename(url: str) -> str:
    """Derive a stable, filesystem-safe name from a URL."""
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    ext_match = re.search(r"\.(png|jpg|jpeg|webp)(?:\?|$)", url, re.IGNORECASE)
    ext = ("." + ext_match.group(1).lower()) if ext_match else ".bin"
    return f"img_{h}{ext}"


class ImageService:
    """Download and cache launch images."""

    def __init__(
        self,
        http: HttpClient,
        cache: ImageCache,
        fallback_path: str | os.PathLike[str],
        priority: list[str] | None = None,
    ) -> None:
        self.http = http
        self.cache = cache
        self.fallback_path = Path(fallback_path)
        self.priority = priority or [
            "rocket_image_url",
            "mission_patch_url",
            "launch_artwork_url",
            "launchpad_image_url",
        ]

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def best_image_for(self, launch: Launch) -> dict[str, Any] | None:
        """Pick and fetch the best available image for ``launch``.

        Returns a dict with keys:
            - ``url``: the URL we tried
            - ``source``: which priority slot it came from
            - ``local_path``: absolute path on disk of the cached file
        or None if no image is available at all (not even the fallback).
        """
        for attr in self.priority:
            url = getattr(launch, attr, "")
            if not url:
                continue
            try:
                path = self._download(url)
                if path is not None:
                    return {
                        "url": url,
                        "source": attr,
                        "local_path": str(path),
                    }
            except (HTTPError, OSError) as exc:
                logger.warning("Image fetch failed for %s (%s): %s", url, attr, exc)
        # Try fallback
        return self._fallback()

    # ------------------------------------------------------------------ #
    # Internals                                                           #
    # ------------------------------------------------------------------ #

    def _download(self, url: str) -> Path | None:
        key = _safe_filename(url)
        cached = self.cache.get(key)
        if cached is not None:
            return self.cache.path_for(key)
        data = self.http.get_bytes(url)
        if len(data) > MAX_BYTES:
            logger.warning("Image %s is too large (%d bytes), skipping", url, len(data))
            return None
        return self.cache.put(key, data)

    def _fallback(self) -> dict[str, Any] | None:
        if self.fallback_path.is_file():
            return {
                "url": "",
                "source": "fallback",
                "local_path": str(self.fallback_path.resolve()),
            }
        logger.warning("No fallback image bundled at %s", self.fallback_path)
        return None
