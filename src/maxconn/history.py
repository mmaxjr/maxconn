from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from maxconn._file_lock import locked
from maxconn._redact import redact as _redact
from maxconn.hosts import DEFAULT_BASE_DIR

_RELATIVE_SINCE_PATTERN = re.compile(r"^(\d+)([hd])$")


def parse_since(value: str, *, now: datetime | None = None) -> datetime:
    """Parse a ``--since`` value into a UTC datetime.

    Accepts ``today``, ``yesterday``, a relative offset like ``24h``/``7d``,
    or an ISO date/datetime (interpreted as UTC if it carries no timezone,
    matching how HistoryEntry.timestamp itself is always stored in UTC).
    """
    reference = now if now is not None else datetime.now(timezone.utc)
    normalized = value.strip().lower()
    if normalized == "today":
        return reference.replace(hour=0, minute=0, second=0, microsecond=0)
    if normalized == "yesterday":
        return reference.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    match = _RELATIVE_SINCE_PATTERN.match(normalized)
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        delta = timedelta(hours=amount) if unit == "h" else timedelta(days=amount)
        return reference - delta
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"could not parse --since value: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


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
        with locked(self.history_path):
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
        last_line = self._read_last_line()
        if last_line is None:
            return 1
        return int(json.loads(last_line)["id"]) + 1

    def _read_last_line(self) -> str | None:
        if not self.history_path.exists():
            return None
        block_size = 4096
        with self.history_path.open("rb") as handle:
            handle.seek(0, 2)
            file_size = handle.tell()
            if file_size == 0:
                return None
            data = b""
            position = file_size
            while position > 0:
                read_size = min(block_size, position)
                position -= read_size
                handle.seek(position)
                data = handle.read(read_size) + data
                if b"\n" in data.rstrip(b"\n"):
                    break
        trimmed = data.rstrip(b"\n")
        last_line = trimmed[trimmed.rfind(b"\n") + 1 :]
        if not last_line.strip():
            return None
        return last_line.decode("utf-8")


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


def format_history_csv(entries: list[HistoryEntry]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "timestamp", "alias", "host", "port", "protocol", "username", "status", "command"])
    for entry in entries:
        writer.writerow(
            [
                entry.id,
                entry.timestamp,
                entry.alias or "",
                entry.host,
                "" if entry.port is None else entry.port,
                entry.protocol,
                entry.username or "",
                "ok" if entry.ok else "fail",
                "" if entry.command is None else entry.command,
            ]
        )
    return output.getvalue()


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
