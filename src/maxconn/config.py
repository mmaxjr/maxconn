from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maxconn._file_lock import locked
from maxconn.hosts import DEFAULT_BASE_DIR

ALLOWED_KEYS = ("timeout", "concurrency", "workers", "ports", "audit_log", "update_notify")


class ConfigStore:
    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else DEFAULT_BASE_DIR
        self.config_path = self.base_dir / "config.json"

    def load(self) -> dict[str, str]:
        if not self.config_path.exists():
            return {}
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def set(self, key: str, value: str) -> None:
        if key not in ALLOWED_KEYS:
            raise ValueError(f"unknown config key: {key!r}; allowed: {', '.join(ALLOWED_KEYS)}")
        with locked(self.config_path):
            data = self.load()
            data[key] = value
            self._write(data)

    def get(self, key: str) -> str | None:
        return self.load().get(key)

    def unset(self, key: str) -> None:
        with locked(self.config_path):
            data = self.load()
            data.pop(key, None)
            self._write(data)

    def _write(self, data: dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
