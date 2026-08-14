from __future__ import annotations

import json
from pathlib import Path

from maxconn.hosts import DEFAULT_BASE_DIR


def config_path(base_dir: str | Path | None = None) -> Path:
    base = Path(base_dir) if base_dir is not None else DEFAULT_BASE_DIR
    return base / "config.json"


def load_theme(base_dir: str | Path | None = None) -> str | None:
    path = config_path(base_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("theme")
    except (OSError, ValueError):
        return None


def save_theme(name: str, base_dir: str | Path | None = None) -> None:
    path = config_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"theme": name}, indent=2), encoding="utf-8")
