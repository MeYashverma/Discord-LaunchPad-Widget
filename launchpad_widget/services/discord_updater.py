"""Push the built payload to Discord.

The endpoint we hit is:

    PATCH https://discord.com/api/v9/applications/{APP_ID}/users/{USER_ID}/identities/0/profile

The body must be a JSON object with an ``identities`` key. Authorization is
``Bot <token>`` (a user-token variant also works in some setups but ``Bot``
is the supported path).

We also implement Discord's documented rate-limit response: a 429 with a
``Retry-After`` header is honoured before raising.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

from ..config import DISCORD_IDENTITY_URL
from ..utils.http_client import HttpClient, HTTPError

logger = logging.getLogger(__name__)


class DiscordUpdater:
    def __init__(
        self,
        http: HttpClient,
        *,
        app_id: str,
        user_id: str,
        bot_token: str,
        dry_run: bool = False,
        state_file: str | Path | None = None,
    ) -> None:
        self.http = http
        self.app_id = app_id
        self.user_id = user_id
        self.bot_token = bot_token
        self.dry_run = dry_run
        self.state_file = Path(state_file) if state_file else None
        self._last_signature: str | None = None

    @property
    def url(self) -> str:
        return DISCORD_IDENTITY_URL.format(app_id=self.app_id, user_id=self.user_id)

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def push(self, payload: dict[str, Any]) -> bool:
        """Send the payload. Returns True on success (or a meaningful dry run)."""
        signature = self._signature(payload)
        if self._last_signature == signature and self._already_pushed(signature):
            logger.info("Payload unchanged since last PATCH; skipping.")
            return True

        if self.dry_run:
            logger.info("DRY_RUN: would PATCH %s with payload: %s",
                        self.url, json.dumps(payload)[:500])
            self._record_success(signature)
            return True

        if not self.bot_token:
            raise HTTPError("DISCORD_BOT_TOKEN is required for non-dry-run updates")

        body = json.dumps(payload).encode("utf-8")
        # The session header is "application/json" by default but let's be explicit
        headers = {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json",
        }
        try:
            resp = self.http.session.patch(self.url, data=body, headers=headers,
                                           timeout=self.http.timeout)
        except requests.RequestException as exc:
            raise HTTPError(f"Network error during PATCH: {exc}") from exc

        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", "1"))
            logger.warning("Discord 429 — sleeping %.2fs before raising", retry_after)
            time.sleep(retry_after)
            raise HTTPError(f"429 from Discord (retry after {retry_after}s)")

        if 200 <= resp.status_code < 300:
            logger.info("PATCH ok (%d) for %s", resp.status_code, self.url)
            self._record_success(signature)
            return True

        # 4xx / 5xx
        raise HTTPError(
            f"Discord PATCH failed: {resp.status_code} {resp.reason} — {resp.text[:300]}"
        )

    # ------------------------------------------------------------------ #
    # State / de-duplication                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _signature(payload: dict[str, Any]) -> str:
        """Stable hash of the payload, used to skip redundant PATCH calls."""
        import hashlib
        canon = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    def _already_pushed(self, signature: str) -> bool:
        if self.state_file is None or not self.state_file.exists():
            return False
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return data.get("signature") == signature

    def _record_success(self, signature: str) -> None:
        self._last_signature = signature
        if self.state_file is None:
            return
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(
                json.dumps({"signature": signature, "at": time.time()}),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Could not write state file %s: %s", self.state_file, exc)
