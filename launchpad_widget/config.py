"""Configuration loader for the Discord LaunchPad Widget.

Configuration values may be provided in two ways (in priority order):

1. Environment variables (preferred for hosted / GitHub Actions runs).
2. A ``config.json`` file located next to the entry point script.

This module is intentionally defensive: missing values are filled in with
sensible defaults so that the widget can boot in a degraded state and log
warnings about what is missing.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Discord Dynamic Identity PATCH endpoint base
DISCORD_IDENTITY_URL = (
    "https://discord.com/api/v9/applications/{app_id}/users/{user_id}/identities/0/profile"
)
DISCORD_API_BASE = "https://discord.com/api/v9"

# Free, no-auth launch data sources
SPACEX_API_BASE = "https://api.spacexdata.com/v4"
LAUNCH_LIBRARY_BASE = "https://ll.thespacedevs.com/2.3.0"
NASA_API_BASE = "https://api.nasa.gov"
WTIA_BASE = "https://api.wheretheiss.at/v1"
OPEN_NOTIFY_BASE = "http://api.open-notify.org"


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s=%r, using default %s", name, raw, default)
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid int for %s=%r, using default %s", name, raw, default)
        return default


def _env_str(name: str, default: str = "") -> str:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class AppConfig:
    """Top-level configuration for the widget updater."""

    # Discord credentials
    discord_app_id: str = ""
    discord_user_id: str = ""
    discord_bot_token: str = ""

    # Source preference
    preferred_source: str = "launch_library"  # "launch_library" or "spacex"

    # Loop timing
    update_interval_seconds: float = 300.0
    min_patch_interval_seconds: float = 60.0
    max_runtime_seconds: float = 21000.0  # ~5h50m

    # Caching
    cache_ttl_seconds: float = 120.0
    image_cache_ttl_seconds: float = 86400.0  # 1 day for images

    # HTTP
    http_timeout_seconds: float = 20.0
    http_retries: int = 3
    http_backoff_factor: float = 1.5

    # Image handling
    image_priority: list[str] = field(
        default_factory=lambda: ["rocket", "mission_patch", "launch_artwork", "launchpad"]
    )
    fallback_image_path: str = "launchpad_widget/assets/fallback.png"

    # Runtime
    dry_run: bool = False
    log_file: str = "widget.log"
    log_level: str = "INFO"
    state_file: str = "last_payload.json"

    # Optional NASA key (free tier works without one, but rate-limited)
    nasa_api_key: str = "DEMO_KEY"

    # Extra metadata to show in the widget
    show_iss_bonus: bool = False

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "AppConfig":
        """Load config from environment variables and (optionally) a JSON file."""
        file_data: dict[str, Any] = {}
        if config_path is None:
            config_path = os.environ.get("LAUNCHPAD_CONFIG", "config.json")
        try:
            path = Path(config_path)
            if path.is_file():
                file_data = json.loads(path.read_text(encoding="utf-8"))
                logger.info("Loaded configuration from %s", path)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read config file %s: %s", config_path, exc)

        cfg = cls(
            discord_app_id=_env_str("DISCORD_APPLICATION_ID", file_data.get("discord_app_id", "")),
            discord_user_id=_env_str("DISCORD_USER_ID", file_data.get("discord_user_id", "")),
            discord_bot_token=_env_str(
                "DISCORD_BOT_TOKEN", file_data.get("discord_bot_token", "")
            ),
            preferred_source=_env_str(
                "PREFERRED_SOURCE", file_data.get("preferred_source", "launch_library")
            ).lower(),
            update_interval_seconds=_env_float(
                "UPDATE_INTERVAL_SECONDS",
                float(file_data.get("update_interval_seconds", 300)),
            ),
            min_patch_interval_seconds=_env_float(
                "MIN_PATCH_INTERVAL_SECONDS",
                float(file_data.get("min_patch_interval_seconds", 60)),
            ),
            max_runtime_seconds=_env_float(
                "MAX_RUNTIME_SECONDS",
                float(file_data.get("max_runtime_seconds", 21000)),
            ),
            cache_ttl_seconds=_env_float(
                "CACHE_TTL_SECONDS",
                float(file_data.get("cache_ttl_seconds", 120)),
            ),
            image_cache_ttl_seconds=_env_float(
                "IMAGE_CACHE_TTL_SECONDS",
                float(file_data.get("image_cache_ttl_seconds", 86400)),
            ),
            http_timeout_seconds=_env_float(
                "HTTP_TIMEOUT_SECONDS",
                float(file_data.get("http_timeout_seconds", 20)),
            ),
            http_retries=_env_int("HTTP_RETRIES", int(file_data.get("http_retries", 3))),
            http_backoff_factor=_env_float(
                "HTTP_BACKOFF_FACTOR",
                float(file_data.get("http_backoff_factor", 1.5)),
            ),
            image_priority=file_data.get(
                "image_priority",
                ["rocket", "mission_patch", "launch_artwork", "launchpad"],
            ),
            fallback_image_path=_env_str(
                "FALLBACK_IMAGE_PATH",
                file_data.get("fallback_image_path", "launchpad_widget/assets/fallback.png"),
            ),
            dry_run=_env_bool("DRY_RUN", bool(file_data.get("dry_run", False))),
            log_file=_env_str("LOG_FILE", file_data.get("log_file", "widget.log")),
            log_level=_env_str("LOG_LEVEL", file_data.get("log_level", "INFO")).upper(),
            state_file=_env_str("STATE_FILE", file_data.get("state_file", "last_payload.json")),
            nasa_api_key=_env_str("NASA_API_KEY", file_data.get("nasa_api_key", "DEMO_KEY")),
            show_iss_bonus=_env_bool(
                "SHOW_ISS_BONUS", bool(file_data.get("show_iss_bonus", False))
            ),
        )
        return cfg

    def validate(self) -> list[str]:
        """Return a list of human-readable problems. Empty list = valid."""
        problems: list[str] = []
        if not self.discord_app_id:
            problems.append("DISCORD_APPLICATION_ID is not set")
        if not self.discord_user_id:
            problems.append("DISCORD_USER_ID is not set")
        if not self.discord_bot_token and not self.dry_run:
            problems.append("DISCORD_BOT_TOKEN is not set (required unless DRY_RUN=true)")
        if self.preferred_source not in ("launch_library", "spacex"):
            problems.append(
                f"PREFERRED_SOURCE must be 'launch_library' or 'spacex', "
                f"got {self.preferred_source!r}"
            )
        return problems
