"""Image service: pick, download, cache the best image for a launch."""

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


MAX_BYTES = 5 * 1024 * 1024  # 5 MB Discord limit


def _safe_filename(url: str) -> str:
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    ext_match = re.search(r"\.(png|jpg|jpeg|webp)(?:\?|$)", url, re.IGNORECASE)
    ext = ("." + ext_match.group(1).lower()) if ext_match else ".bin"
    return f"img_{h}{ext}"


class ImageService:
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
        # Map short names used in config to actual Launch dataclass fields.
        # Users can write either short (``"rocket"``) or full
        # (``"rocket_image_url"``) names in config.
        self.priority = priority or [
            "rocket",
            "mission_patch",
            "launch_artwork",
            "launchpad",
        ]
        self._attr_map = {
            "rocket": "rocket_image_url",
            "mission_patch": "mission_patch_url",
            "launch_artwork": "launch_artwork_url",
            "launchpad": "launchpad_image_url",
            # Also accept the full field names directly
            "rocket_image_url": "rocket_image_url",
            "mission_patch_url": "mission_patch_url",
            "launch_artwork_url": "launch_artwork_url",
            "launchpad_image_url": "launchpad_image_url",
        }

    def best_image_for(self, launch: Launch) -> dict[str, Any] | None:
        """Return {"url", "source", "local_path"} or None."""
        for name in self.priority:
            attr = self._attr_map.get(name, name)
            url = getattr(launch, attr, "")
            if not url:
                continue
            try:
                path = self._download(url)
                if path is not None:
                    return {
                        "url": url,
                        "source": name,
                        "local_path": str(path),
                    }
            except (HTTPError, OSError) as exc:
                logger.warning("Image fetch failed for %s (%s): %s", url, name, exc)
        return self._fallback()

    def _download(self, url: str) -> Path | None:
        key = _safe_filename(url)
        cached = self.cache.get(key)
        if cached is not None:
            return self.cache.path_for(key)
        data = self.http.get_bytes(url)
        if len(data) > MAX_BYTES:
            logger.warning("Image %s too large (%d bytes), skipping", url, len(data))
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
