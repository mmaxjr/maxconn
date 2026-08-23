from __future__ import annotations

import builtins
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from maxconn._file_lock import locked
from maxconn.hosts import DEFAULT_BASE_DIR


@dataclass(frozen=True)
class SnippetEntry:
    name: str
    tags: list[str]
    created: str
    updated: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "tags", list(self.tags or []))


class SnippetStore:
    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else DEFAULT_BASE_DIR
        self.index_path = self.base_dir / "snippets_index.json"
        self.snippets_dir = self.base_dir / "snippets"

    def add(self, name: str, content: str, *, tags: builtins.list[str] | None = None) -> SnippetEntry:
        with locked(self.index_path):
            entries = {entry.name: entry for entry in self.list()}
            if name in entries:
                raise ValueError(f"snippet already exists: {name}")
            now = _now()
            entry = SnippetEntry(name=name, tags=tags or [], created=now, updated=now)
            entries[name] = entry
            self._write_content(name, content)
            self._write_index(list(entries.values()))
            return entry

    def list(self, *, tag: str | None = None) -> builtins.list[SnippetEntry]:
        entries = sorted(
            (self._entry_from_dict(item) for item in self._read_json()),
            key=lambda entry: entry.name,
        )
        if tag:
            entries = [entry for entry in entries if tag in entry.tags]
        return entries

    def get(self, name: str) -> tuple[SnippetEntry, str]:
        for entry in self.list():
            if entry.name == name:
                return entry, self._read_content(name)
        raise KeyError(f"snippet not found: {name}")

    def edit(self, name: str, content: str, *, tags: builtins.list[str] | None = None) -> SnippetEntry:
        with locked(self.index_path):
            entries = {entry.name: entry for entry in self.list()}
            if name not in entries:
                raise KeyError(f"snippet not found: {name}")
            existing = entries[name]
            updated = replace(existing, tags=tags if tags is not None else existing.tags, updated=_now())
            entries[name] = updated
            self._write_content(name, content)
            self._write_index(list(entries.values()))
            return updated

    def remove(self, name: str) -> None:
        with locked(self.index_path):
            entries = self.list()
            filtered = [entry for entry in entries if entry.name != name]
            if len(filtered) == len(entries):
                raise KeyError(f"snippet not found: {name}")
            self._write_index(filtered)
            self._content_path(name).unlink(missing_ok=True)

    def _content_path(self, name: str) -> Path:
        return self.snippets_dir / f"{_safe_filename(name)}.txt"

    def _read_content(self, name: str) -> str:
        path = self._content_path(name)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _write_content(self, name: str, content: str) -> None:
        path = self._content_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _read_json(self) -> builtins.list[dict[str, Any]]:
        if not self.index_path.exists():
            return []
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise TypeError(f"invalid maxconn data file: {self.index_path}")
        return data

    def _write_index(self, entries: builtins.list[SnippetEntry]) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps([asdict(entry) for entry in entries], indent=2, sort_keys=True), encoding="utf-8"
        )

    def _entry_from_dict(self, data: dict[str, Any]) -> SnippetEntry:
        return SnippetEntry(
            name=str(data["name"]),
            tags=[str(tag) for tag in data.get("tags", [])],
            created=str(data["created"]),
            updated=str(data["updated"]),
        )


def format_snippets_table(entries: list[SnippetEntry]) -> str:
    rows = [[entry.name, ",".join(entry.tags), entry.updated] for entry in entries]
    return _format_table(["NAME", "TAGS", "UPDATED"], rows)


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [
        max(len(header), *(len(row[index]) for row in rows)) if rows else len(header)
        for index, header in enumerate(headers)
    ]
    lines = [_format_row(headers, widths)]
    lines.extend(_format_row(row, widths) for row in rows)
    return "\n".join(lines)


def _format_row(values: list[str], widths: list[int]) -> str:
    return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values)).rstrip()


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
