"""Thin, opinionated HTTP client wrapper.

A single ``requests.Session`` is reused for connection pooling. All GETs go
through ``get_json`` which:

* sets a sensible timeout,
* retries transient failures (network errors, 5xx, 429) with exponential
  backoff,
* raises ``HTTPError`` for non-recoverable 4xx responses,
* transparently honours a ``Retry-After`` header when present.

JSON decoding errors are treated as fatal — they almost always indicate a
genuine upstream bug.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from .retry import call_with_retries

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Discord-LaunchPad-Widget/1.0 (+https://github.com/MeYashverma/Discord-LaunchPad-Widget)",
    "Accept": "application/json",
}


class HTTPError(RuntimeError):
    """Raised when an HTTP request fails in a way we don't want to retry."""


class HttpClient:
    """A small wrapper around ``requests.Session`` with retries and timeouts."""

    def __init__(
        self,
        *,
        timeout: float = 20.0,
        retries: int = 3,
        backoff_factor: float = 1.5,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.session = requests.Session()
        merged = dict(DEFAULT_HEADERS)
        if headers:
            merged.update(headers)
        self.session.headers.update(merged)

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """GET ``url`` and return the decoded JSON body."""
        def do_request() -> Any:
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException:
                # let retry helper decide
                raise
            if resp.status_code == 429:
                # honour Retry-After if the server gave us one
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        import time
                        wait = max(float(retry_after), 0.0)
                        logger.warning("Rate limited on %s, sleeping %.1fs", url, wait)
                        time.sleep(min(wait, 30.0))
                    except ValueError:
                        pass
                # bubble up so the retry helper catches it
                raise requests.HTTPError(f"429 from {url}", response=resp)
            if 500 <= resp.status_code < 600:
                raise requests.HTTPError(
                    f"{resp.status_code} from {url}: {resp.text[:200]}",
                    response=resp,
                )
            if resp.status_code >= 400:
                # 4xx other than 429: not retryable
                raise HTTPError(
                    f"{resp.status_code} from {url}: {resp.text[:200]}"
                )
            try:
                return resp.json()
            except ValueError as exc:
                raise HTTPError(f"Could not decode JSON from {url}: {exc}") from exc

        return call_with_retries(
            do_request,
            attempts=self.retries,
            backoff_factor=self.backoff_factor,
            label=f"GET {url}",
        )

    def get_bytes(self, url: str) -> bytes:
        """GET ``url`` and return raw bytes (used for image downloads)."""
        def do_request() -> bytes:
            try:
                resp = self.session.get(url, timeout=self.timeout)
            except requests.RequestException:
                raise
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        import time
                        wait = max(float(retry_after), 0.0)
                        logger.warning("Rate limited on %s, sleeping %.1fs", url, wait)
                        time.sleep(min(wait, 30.0))
                    except ValueError:
                        pass
                raise requests.HTTPError(f"429 from {url}", response=resp)
            if 500 <= resp.status_code < 600:
                raise requests.HTTPError(
                    f"{resp.status_code} from {url}", response=resp
                )
            if resp.status_code >= 400:
                raise HTTPError(f"{resp.status_code} from {url}")
            return resp.content

        return call_with_retries(
            do_request,
            attempts=self.retries,
            backoff_factor=self.backoff_factor,
            label=f"GET (bytes) {url}",
        )

    def patch_json(self, url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> requests.Response:
        """PATCH a JSON payload. No internal retry — Discord rate limits are
        handled by the caller so we can be precise about backoff."""
        merged_headers = dict(self.session.headers)
        if headers:
            merged_headers.update(headers)
        try:
            return self.session.patch(url, json=payload, headers=merged_headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise HTTPError(f"PATCH {url} failed: {exc}") from exc

    def close(self) -> None:
        self.session.close()
