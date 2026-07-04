"""File-backed TTL caches for API data and downloaded images."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TTLCache:
    """Per-key TTL cache, persisted to a JSON file."""

    def __init__(self, path: str | os.PathLike[str], default_ttl: float = 120.0) -> None:
        self.path = Path(path)
        self.default_ttl = default_ttl
        self._data: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            return
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Cache %s unreadable, starting empty: %s", self.path, exc)
            self._data = {}

    def _persist(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(self._data), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            logger.warning("Could not persist cache %s: %s", self.path, exc)

    def get(self, key: str) -> Any | None:
        self._load()
        entry = self._data.get(key)
        if not entry:
            return None
        if float(entry.get("expires_at", 0)) < time.time():
            self._data.pop(key, None)
            return None
        return entry.get("value")

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        self._load()
        ttl = ttl if ttl is not None else self.default_ttl
        self._data[key] = {"value": value, "expires_at": time.time() + ttl}
        self._persist()

    def clear(self) -> None:
        self._data = {}
        self._persist()


class ImageCache:
    """On-disk image cache, indexed by content hash."""

    def __init__(self, directory: str | os.PathLike[str], default_ttl: float = 86400.0) -> None:
        self.directory = Path(directory)
        self.default_ttl = default_ttl
        self.directory.mkdir(parents=True, exist_ok=True)
        self.index_path = self.directory / "index.json"
        self._index: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.index_path.exists():
            return
        try:
            self._index = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Image cache index unreadable: %s", exc)
            self._index = {}

    def _persist(self) -> None:
        try:
            tmp = self.index_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._index), encoding="utf-8")
            tmp.replace(self.index_path)
        except OSError as exc:
            logger.warning("Could not persist image cache index: %s", exc)

    def has_fresh(self, key: str) -> bool:
        self._load()
        entry = self._index.get(key)
        if not entry:
            return False
        return float(entry.get("expires_at", 0)) >= time.time()

    def path_for(self, key: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
        return self.directory / f"{safe}.bin"

    def get(self, key: str) -> bytes | None:
        if not self.has_fresh(key):
            return None
        path = self.path_for(key)
        if not path.exists():
            return None
        try:
            return path.read_bytes()
        except OSError as exc:
            logger.warning("Failed to read cached image %s: %s", key, exc)
            return None

    def put(self, key: str, data: bytes, ttl: float | None = None) -> Path:
        self._load()
        ttl = ttl if ttl is not None else self.default_ttl
        path = self.path_for(key)
        try:
            path.write_bytes(data)
        except OSError as exc:
            logger.warning("Failed to write image %s: %s", path, exc)
        self._index[key] = {
            "path": str(path),
            "size": len(data),
            "expires_at": time.time() + ttl,
        }
        self._persist()
        return path
