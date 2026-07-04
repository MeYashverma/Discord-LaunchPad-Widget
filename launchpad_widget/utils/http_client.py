"""Thin HTTP client wrapper with retries and 429 handling."""

from __future__ import annotations

import logging
from typing import Any

import requests

from .retry import call_with_retries

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Discord-LaunchPad-Widget/1.0",
    "Accept": "application/json",
}


class HTTPError(RuntimeError):
    pass


class HttpClient:
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
        def do_request() -> Any:
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException:
                raise
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        import time as _t
                        wait = max(float(retry_after), 0.0)
                        logger.warning("Rate limited on %s, sleeping %.1fs", url, wait)
                        _t.sleep(min(wait, 30.0))
                    except ValueError:
                        pass
                raise requests.HTTPError(f"429 from {url}", response=resp)
            if 500 <= resp.status_code < 600:
                raise requests.HTTPError(
                    f"{resp.status_code} from {url}: {resp.text[:200]}",
                    response=resp,
                )
            if resp.status_code >= 400:
                raise HTTPError(f"{resp.status_code} from {url}: {resp.text[:200]}")
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
        def do_request() -> bytes:
            try:
                resp = self.session.get(url, timeout=self.timeout)
            except requests.RequestException:
                raise
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        import time as _t
                        wait = max(float(retry_after), 0.0)
                        logger.warning("Rate limited on %s, sleeping %.1fs", url, wait)
                        _t.sleep(min(wait, 30.0))
                    except ValueError:
                        pass
                raise requests.HTTPError(f"429 from {url}", response=resp)
            if 500 <= resp.status_code < 600:
                raise requests.HTTPError(f"{resp.status_code} from {url}", response=resp)
            if resp.status_code >= 400:
                raise HTTPError(f"{resp.status_code} from {url}")
            return resp.content

        return call_with_retries(
            do_request,
            attempts=self.retries,
            backoff_factor=self.backoff_factor,
            label=f"GET (bytes) {url}",
        )

    def post_multipart(
        self,
        url: str,
        files: dict[str, tuple[str, Any, str]],
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> requests.Response:
        merged_headers = dict(self.session.headers)
        if headers:
            merged_headers.update(headers)
        try:
            return self.session.post(url, files=files, headers=merged_headers, timeout=timeout)
        except requests.RequestException as exc:
            raise HTTPError(f"POST {url} failed: {exc}") from exc

    def close(self) -> None:
        self.session.close()
