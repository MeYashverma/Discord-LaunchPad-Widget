"""Top-level orchestrator."""

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
from .dwif_runner import process_image as dwif_process
from .image_service import ImageService
from .payload_builder import PayloadBuilder

logger = logging.getLogger(__name__)


class ImageUploader:
    """Uploads a local image to a Discord channel, returns the CDN URL."""

    def __init__(self, *, bot_token: str, channel_id: str, http: HttpClient) -> None:
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.http = http

    def upload(self, local_path: str) -> str | None:
        if not local_path or not Path(local_path).is_file():
            return None
        url = f"https://discord.com/api/v9/channels/{self.channel_id}/messages"
        path = Path(local_path)
        try:
            with path.open("rb") as f:
                files = {
                    "files[0]": (path.name, f, "application/octet-stream"),
                }
                resp = self.http.post_multipart(
                    url,
                    files=files,
                    headers={"Authorization": f"Bot {self.bot_token}"},
                    timeout=30.0,
                )
        except HTTPError as exc:
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
        use_dwif: bool = True,
    ) -> None:
        self.config = config
        self.http = http
        self.image_service = image_service
        self.payload_builder = payload_builder
        self.updater = updater
        self.providers = providers
        self.image_uploader = image_uploader
        self.use_dwif = use_dwif
        self.api_cache = TTLCache("cache/launches.json", default_ttl=config.cache_ttl_seconds)
        self._stop_requested = False
        self._last_patch_at: float = 0.0
        self._current_launch_id: str | None = None

    def request_stop(self, *_: Any) -> None:
        logger.info("Stop requested, finishing current cycle then exiting")
        self._stop_requested = True

    def install_signal_handlers(self) -> None:
        try:
            signal.signal(signal.SIGINT, self.request_stop)
            signal.signal(signal.SIGTERM, self.request_stop)
        except (ValueError, OSError):
            pass

    def run(self) -> None:
        self.install_signal_handlers()
        started = time.time()
        logger.info(
            "Starting orchestrator: interval=%.0fs, runtime budget=%.0fs, "
            "dry_run=%s, image_uploader=%s, dwif=%s",
            self.config.update_interval_seconds,
            self.config.max_runtime_seconds,
            self.config.dry_run,
            "enabled" if self.image_uploader else "disabled",
            "enabled" if self.use_dwif else "disabled",
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

            sleep_for = min(self.config.update_interval_seconds, budget_left)
            slept = 0.0
            while slept < sleep_for and not self._stop_requested:
                time.sleep(min(1.0, sleep_for - slept))
                slept += 1.0

    def cycle(self) -> None:
        launch = self._fetch_next_launch()
        if launch is None:
            logger.warning("No upcoming launch found, skipping this cycle")
            return

        if (time.time() - self._last_patch_at) < self.config.min_patch_interval_seconds:
            if self._current_launch_id == launch.external_id:
                logger.info("Within min patch interval and same launch, skipping PATCH")
                return

        image_info = self.image_service.best_image_for(launch)
        if image_info is None:
            logger.warning("No image could be picked (incl. fallback); sending without image")
            image_info = {"url": "", "source": "none", "local_path": ""}

        # 1. Run D.W.I.F (Discord Widget Image Fixer) on the picked image to
        #    add the transparent top strip and rounded top-right corner.
        #    D.W.I.F also re-saves the file as a proper PNG which makes the
        #    CDN URL look clean (no more ".bin" filenames).
        if image_info.get("local_path") and self.use_dwif:
            processed = dwif_process(image_info["local_path"])
            if processed:
                image_info = dict(image_info)
                image_info["local_path"] = str(processed)
                image_info["source"] = (
                    f"{image_info.get('source', 'image')}+dwif"
                )

        # 2. Upload the styled image to Discord and grab a cdn.discordapp.com URL.
        if (
            image_info.get("local_path")
            and self.image_uploader is not None
            and not self.config.dry_run
        ):
            cdn_url = self.image_uploader.upload(image_info["local_path"])
            if cdn_url:
                image_info = dict(image_info)
                image_info["cdn_url"] = cdn_url

        # 3. Build the Discord identity payload and PATCH the widget.
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

    def _fetch_next_launch(self) -> Launch | None:
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

    @staticmethod
    def _summarise(launch: Launch, image_info: dict[str, Any] | None) -> None:
        img = image_info.get("source", "\u2014") if image_info else "\u2014"
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


def build_default_orchestrator(config: AppConfig) -> WidgetOrchestrator:
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
    payload_builder = PayloadBuilder()
    updater = DiscordUpdater(
        http_session=http.session,
        app_id=config.discord_app_id,
        user_id=config.discord_user_id,
        bot_token=config.discord_bot_token,
        dry_run=config.dry_run,
        state_file=config.state_file,
        timeout=config.http_timeout_seconds,
    )
    providers: list[LaunchProvider] = [
        LaunchLibrary2Provider(http=http),
        SpaceXProvider(http=http),
    ]
    image_uploader: ImageUploader | None = None
    if config.discord_target_channel_id and config.discord_bot_token and not config.dry_run:
        image_uploader = ImageUploader(
            bot_token=config.discord_bot_token,
            channel_id=config.discord_target_channel_id,
            http=http,
        )
        logger.info("Image uploader enabled → channel %s", config.discord_target_channel_id)

    return WidgetOrchestrator(
        config=config,
        http=http,
        image_service=image_service,
        payload_builder=payload_builder,
        updater=updater,
        providers=providers,
        image_uploader=image_uploader,
        use_dwif=True,
    )
