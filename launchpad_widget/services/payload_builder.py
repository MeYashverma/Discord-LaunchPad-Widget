"""Top-level orchestrator: glues providers, image service, builder, and updater.

The orchestrator owns the long-lived loop and is the only thing the entry
point needs to instantiate. It also handles:

* the runtime budget (so we can self-restart before GitHub Actions kills us),
* graceful Ctrl+C,
* swapping to the next valid launch when the current one scrubs / launches,
* logging of every step at INFO level.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..apis import LaunchLibrary2Provider, SpaceXProvider
from ..apis.base import LaunchProvider
from ..config import AppConfig
from ..models import Launch
from ..utils.cache import TTLCache
from ..utils.http_client import HTTPError, HttpClient
from .discord_updater import DiscordUpdater
from .image_service import ImageService
from .payload_builder import PayloadBuilder

logger = logging.getLogger(__name__)


class ImageUploader:
    """Optional helper that uploads a local image to Discord and returns the CDN URL.

    It is plugged into the orchestrator only when
    ``DISCORD_TARGET_CHANNEL_ID`` is set. The Discord CDN URL the upload
    returns is what we put in the widget's ``type: 3`` image field.
    """

    def __init__(self, *, bot_token: str, channel_id: str) -> None:
        self.bot_token = bot_token
        self.channel_id = channel_id

    def upload(self, local_path: str) -> str | None:
        """Upload ``local_path`` and return the CDN URL, or None on failure."""
        import requests
        if not local_path or not Path(local_path).is_file():
            return None
        url = f"https://discord.com/api/v9/channels/{self.channel_id}/messages"
        headers = {"Authorization": f"Bot {self.bot_token}"}
        try:
            with open(local_path, "rb") as f:
                files = {"files[0]": (Path(local_path).name, f, "application/octet-stream")}
                resp = requests.post(url, headers=headers, files=files, timeout=30)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Image upload to Discord failed: %s", exc)
            return None
        if not (200 <= resp.status_code < 300):
            logger.warning(
                "Image upload to Discord returned %d: %s",
                resp.status_code, resp.text[:200],
            )
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        attachments = data.get("attachments") or []
        if not attachments:
            return None
        cdn_url = attachments[0].get("url") or ""
        if cdn_url:
            logger.info("Image uploaded to Discord CDN: %s", cdn_url)
        return cdn_url


class WidgetOrchestrator:
    """Drive the widget update loop."""

    def __init__(
        self,
        config: AppConfig,
        *,
        http: HttpClient,
        image_service: ImageService,
        payload_builder: PayloadBuilder,
        updater: DiscordUpdater,
        providers: list[LaunchProvider],
        image_uploader: ImageUploader | None = None,
    ) -> None:
        self.config = config
        self.http = http
        self.image_service = image_service
        self.payload_builder = payload_builder
        self.updater = updater
        self.providers = providers
        self.image_uploader = image_uploader
        self.api_cache = TTLCache("cache/launches.json", default_ttl=config.cache_ttl_seconds)
        self._stop_requested = False
        self._last_patch_at: float = 0.0
        self._current_launch_id: str | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def request_stop(self, *_: Any) -> None:
        logger.info("Stop requested, finishing current cycle then exiting")
        self._stop_requested = True

    def install_signal_handlers(self) -> None:
        try:
            signal.signal(signal.SIGINT, self.request_stop)
            signal.signal(signal.SIGTERM, self.request_stop)
        except (ValueError, OSError):
            # Not in main thread / restricted environment
            pass

    def run(self) -> None:
        """Run the update loop until the runtime budget expires or stop is requested."""
        self.install_signal_handlers()
        started = time.time()
        logger.info(
            "Starting orchestrator: interval=%.0fs, runtime budget=%.0fs, dry_run=%s, image_uploader=%s",
            self.config.update_interval_seconds,
            self.config.max_runtime_seconds,
            self.config.dry_run,
            "enabled" if self.image_uploader else "disabled",
        )
        while not self._stop_requested:
            budget_left = self.config.max_runtime_seconds - (time.time() - started)
            if budget_left <= 0:
                logger.info("Runtime budget exhausted, exiting cleanly")
                break

            try:
                self.cycle()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Cycle failed: %s", exc)

            # Sleep with graceful shutdown support
            sleep_for = min(self.config.update_interval_seconds, budget_left)
            slept = 0.0
            while slept < sleep_for and not self._stop_requested:
                time.sleep(min(1.0, sleep_for - slept))
                slept += 1.0

    # ------------------------------------------------------------------ #
    # One cycle                                                           #
    # ------------------------------------------------------------------ #

    def cycle(self) -> None:
        """Fetch → normalize → image → build → PATCH."""
        launch = self._fetch_next_launch()
        if launch is None:
            logger.warning("No upcoming launch found, skipping this cycle")
            return

        # Throttle Discord PATCHes to at most one per min_patch_interval
        if (time.time() - self._last_patch_at) < self.config.min_patch_interval_seconds:
            if self._current_launch_id == launch.external_id:
                logger.info("Within min patch interval and same launch, skipping PATCH")
                return

        image_info = self.image_service.best_image_for(launch)
        if image_info and self.image_uploader is not None and not self.config.dry_run:
            cdn_url = self.image_uploader.upload(image_info["local_path"])
            if cdn_url:
                image_info = dict(image_info)
                image_info["cdn_url"] = cdn_url

        payload = self.payload_builder.build(launch, image_info=image_info)
        try:
            ok = self.updater.push(payload)
        except HTTPError as exc:
            logger.error("PATCH failed: %s", exc)
            return

        if ok:
            self._last_patch_at = time.time()
            self._current_launch_id = launch.external_id
            self._summarise(launch, image_info)

    # ------------------------------------------------------------------ #
    # Fetching / provider selection                                       #
    # ------------------------------------------------------------------ #

    def _fetch_next_launch(self) -> Launch | None:
        """Pick the earliest valid launch from all configured providers.

        We try the preferred source first, then fall back to the others.
        Results are cached per provider for ``cache_ttl_seconds``.
        """
        preferred, fallbacks = self._ordered_providers()
        ordered: list[LaunchProvider] = [preferred] + [p for p in fallbacks if p is not preferred]

        for provider in ordered:
            try:
                cached = self.api_cache.get(f"next:{provider.name}")
                if cached is not None:
                    launches = [Launch.from_dict(item) for item in cached]
                else:
                    launches = provider.next_launches(limit=5)
                    self.api_cache.set(
                        f"next:{provider.name}",
                        [l.to_dict() for l in launches],
                        ttl=self.config.cache_ttl_seconds,
                    )
            except (HTTPError, Exception) as exc:  # noqa: BLE001
                logger.warning("Provider %s failed: %s", provider.name, exc)
                continue

            chosen = self._pick_next_valid(launches)
            if chosen is not None:
                logger.info("Using provider %s, launch %s", provider.name, chosen.mission_name)
                return chosen

        logger.warning("All providers failed to return a valid launch")
        return None

    def _ordered_providers(self) -> tuple[LaunchProvider, list[LaunchProvider]]:
        """Return (preferred, all) based on config.preferred_source."""
        preferred: LaunchProvider | None = None
        all_providers = list(self.providers)
        for p in all_providers:
            if p.name == self.config.preferred_source:
                preferred = p
                break
        if preferred is None and all_providers:
            preferred = all_providers[0]
        return preferred, all_providers  # type: ignore[return-value]

    @staticmethod
    def _pick_next_valid(launches: list[Launch]) -> Launch | None:
        """Pick the earliest launch whose NET is still in the future.

        A launch with status "Success" or a failreason set is treated as
        completed and skipped. A "Hold" status with a future timestamp is
        still useful.
        """
        now = datetime.now(timezone.utc)
        valid: list[tuple[datetime, Launch]] = []
        for l in launches:
            net_str = l.launch_timestamp_utc
            if not net_str:
                continue
            try:
                net = datetime.fromisoformat(net_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            if net < now:
                continue
            if l.failreason:
                continue
            if l.launch_status and l.launch_status.lower() in {
                "launch was a success",
                "launch failure",
                "partial failure",
            }:
                continue
            valid.append((net, l))
        if not valid:
            return None
        valid.sort(key=lambda pair: pair[0])
        return valid[0][1]

    # ------------------------------------------------------------------ #
    # Logging                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _summarise(launch: Launch, image_info: dict[str, Any] | None) -> None:
        img = image_info.get("source", "—") if image_info else "—"
        cdn = " (uploaded)" if image_info and image_info.get("cdn_url") else ""
        logger.info(
            "Updated widget: %s | rocket=%s | provider=%s | status=%s | image=%s%s",
            launch.mission_name,
            launch.rocket_name,
            launch.launch_provider,
            launch.launch_status or "Scheduled",
            img,
            cdn,
        )


# ---------------------------------------------------------------------- #
# Factory                                                                 #
# ---------------------------------------------------------------------- #


def build_default_orchestrator(config: AppConfig) -> WidgetOrchestrator:
    """Build a default orchestrator with sensible production wiring."""
    http = HttpClient(
        timeout=config.http_timeout_seconds,
        retries=config.http_retries,
        backoff_factor=config.http_backoff_factor,
    )

    from ..utils.cache import ImageCache
    image_cache = ImageCache("cache/images", default_ttl=config.image_cache_ttl_seconds)

    image_service = ImageService(
        http=http,
        cache=image_cache,
        fallback_path=config.fallback_image_path,
        priority=config.image_priority,
    )
    payload_builder = PayloadBuilder(image_priority=config.image_priority)
    updater = DiscordUpdater(
        http=http,
        app_id=config.discord_app_id,
        user_id=config.discord_user_id,
        bot_token=config.discord_bot_token,
        dry_run=config.dry_run,
        state_file=config.state_file,
    )

    providers: list[LaunchProvider] = [
        LaunchLibrary2Provider(http=http),
        SpaceXProvider(http=http),
    ]

    image_uploader: ImageUploader | None = None
    target_channel = os.environ.get("DISCORD_TARGET_CHANNEL_ID", "").strip()
    if target_channel and config.discord_bot_token and not config.dry_run:
        image_uploader = ImageUploader(
            bot_token=config.discord_bot_token,
            channel_id=target_channel,
        )
        logger.info("Image uploader enabled → channel %s", target_channel)

    return WidgetOrchestrator(
        config=config,
        http=http,
        image_service=image_service,
        payload_builder=payload_builder,
        updater=updater,
        providers=providers,
        image_uploader=image_uploader,
    )
