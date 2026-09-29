"""Tiny on-disk JSON cache so reruns don't pay for the same searches and fetches."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


class DiskCache:
    def __init__(self, directory: Path | None) -> None:
        self.directory = Path(directory) if directory else None
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, namespace: str, key: str) -> Path | None:
        if not self.directory:
            return None
        digest = hashlib.sha256(f"{namespace}\0{key}".encode()).hexdigest()
        return self.directory / namespace / f"{digest}.json"

    def get(self, namespace: str, key: str, ttl_seconds: int) -> Any | None:
        path = self._path(namespace, key)
        if not path or not path.exists():
            return None
        try:
            payload = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if time.time() - payload.get("t", 0) > ttl_seconds:
            return None
        return payload.get("v")

    def set(self, namespace: str, key: str, value: Any) -> None:
        path = self._path(namespace, key)
        if not path:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"t": time.time(), "v": value}), "utf-8")
        tmp.replace(path)
