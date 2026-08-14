from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from maxconn.hosts import DEFAULT_BASE_DIR

_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(password|passwd|secret|token|key)\s+\S+"),
    re.compile(r"(?i)(--password|--passwd|--secret|--token|--key)\s+\S+"),
)


@dataclass(frozen=True)
class HistoryEntry:
    id: int
    timestamp: str
    alias: str | None
    host: str
    port: int | None
    protocol: str
    username: str | None
    command: str | None
    ok: bool
    exit_status: int | None
    duration: float
    origin: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "protocol", self.protocol.lower())


class HistoryStore:
    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else DEFAULT_BASE_DIR
        self.history_path = self.base_dir / "history.jsonl"

    def record(
        self,
        *,
        alias: str | None,
        host: str,
        port: int | None,
        protocol: str,
        username: str | None,
        command: str | None,
        ok: bool,
        exit_status: int | None,
        duration: float,
        origin: str,
    ) -> HistoryEntry:
        entry = HistoryEntry(
            id=self._next_id(),
            timestamp=_now(),
            alias=alias,
            host=host,
            port=port,
            protocol=protocol,
            username=username,
            command=_redact(command),
            ok=ok,
            exit_status=exit_status,
            duration=duration,
            origin=origin,
        )
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
        return entry

    def list(self) -> list[HistoryEntry]:
        if not self.history_path.exists():
            return []
        entries = []
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(_entry_from_dict(json.loads(line)))
        return entries

    def get(self, entry_id: int) -> HistoryEntry:
        for entry in self.list():
            if entry.id == entry_id:
                return entry
        raise KeyError(f"history entry not found: {entry_id}")

    def clear(self) -> None:
        self.history_path.unlink(missing_ok=True)

    def _next_id(self) -> int:
        entries = self.list()
        return (entries[-1].id + 1) if entries else 1


def format_history_table(entries: list[HistoryEntry]) -> str:
    rows = [
        [
            str(entry.id),
            entry.timestamp,
            entry.alias or "",
            entry.host,
            "" if entry.port is None else str(entry.port),
            entry.protocol,
            entry.username or "",
            "ok" if entry.ok else "fail",
            "" if entry.command is None else entry.command,
        ]
        for entry in entries
    ]
    return _format_table(["ID", "TIME", "ALIAS", "HOST/IP", "PORT", "PROTOCOL", "USER", "STATUS", "COMMAND"], rows)


def _entry_from_dict(data: dict[str, Any]) -> HistoryEntry:
    return HistoryEntry(
        id=int(data["id"]),
        timestamp=str(data["timestamp"]),
        alias=_optional_str(data.get("alias")),
        host=str(data["host"]),
        port=None if data.get("port") is None else int(data["port"]),
        protocol=str(data["protocol"]),
        username=_optional_str(data.get("username")),
        command=_optional_str(data.get("command")),
        ok=bool(data["ok"]),
        exit_status=None if data.get("exit_status") is None else int(data["exit_status"]),
        duration=float(data["duration"]),
        origin=str(data["origin"]),
    )


def _redact(value: str | None) -> str | None:
    if value is None:
        return None
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)} <redacted>", redacted)
    return redacted


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


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
