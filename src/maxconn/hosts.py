from __future__ import annotations

import builtins
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from maxconn._file_lock import locked

DEFAULT_BASE_DIR = Path.home() / ".maxconn"


@dataclass(frozen=True)
class HostEntry:
    name: str
    host: str
    port: int
    protocol: str
    username: str | None = None
    profile: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    password: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "protocol", self.protocol.lower())
        object.__setattr__(self, "tags", list(self.tags or []))


@dataclass(frozen=True)
class SeenHostEntry:
    host: str
    protocol: str
    port: int | None
    username: str | None
    first_seen: str
    last_seen: str
    count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "protocol", self.protocol.lower())


class HostStore:
    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else DEFAULT_BASE_DIR
        self.hosts_path = self.base_dir / "hosts.json"
        self.seen_hosts_path = self.base_dir / "seen_hosts.json"

    def add(self, entry: HostEntry) -> None:
        with locked(self.hosts_path):
            hosts = {host.name: host for host in self.list()}
            hosts[entry.name] = entry
            self._write_hosts(list(hosts.values()))

    def list(self) -> builtins.list[HostEntry]:
        # Annotated as `builtins.list` (not bare `list`) throughout this
        # class: a method named `list` shadows the builtin `list` type for
        # every annotation below it in the class body, since annotations
        # are evaluated lazily (PEP 563 / `from __future__ import
        # annotations`) against the class's own namespace.
        return sorted(
            [self._host_from_dict(item) for item in self._read_json(self.hosts_path)],
            key=lambda entry: entry.name,
        )

    def get(self, name: str) -> HostEntry:
        for entry in self.list():
            if entry.name == name:
                return entry
        raise KeyError(f"host not found: {name}")

    def update(self, name: str, **changes: Any) -> HostEntry:
        with locked(self.hosts_path):
            hosts = {host.name: host for host in self.list()}
            if name not in hosts:
                raise KeyError(f"host not found: {name}")
            updated = replace(hosts[name], **{key: value for key, value in changes.items() if value is not None})
            hosts[name] = updated
            self._write_hosts(list(hosts.values()))
            return updated

    def remove(self, name: str) -> None:
        with locked(self.hosts_path):
            hosts = self.list()
            filtered = [entry for entry in hosts if entry.name != name]
            if len(filtered) == len(hosts):
                raise KeyError(f"host not found: {name}")
            self._write_hosts(filtered)

    def record_seen(
        self,
        host: str,
        *,
        protocol: str,
        port: int | None,
        username: str | None,
    ) -> SeenHostEntry:
        now = _now()
        with locked(self.seen_hosts_path):
            entries = self.list_seen()
            for index, entry in enumerate(entries):
                if (
                    entry.host == host
                    and entry.protocol == protocol.lower()
                    and entry.port == port
                    and entry.username == username
                ):
                    updated = SeenHostEntry(
                        host=entry.host,
                        protocol=entry.protocol,
                        port=entry.port,
                        username=entry.username,
                        first_seen=entry.first_seen,
                        last_seen=now,
                        count=entry.count + 1,
                    )
                    entries[index] = updated
                    self._write_seen(entries)
                    return updated

            created = SeenHostEntry(
                host=host,
                protocol=protocol,
                port=port,
                username=username,
                first_seen=now,
                last_seen=now,
                count=1,
            )
            entries.append(created)
            self._write_seen(entries)
            return created

    def list_seen(self) -> builtins.list[SeenHostEntry]:
        entries = [self._seen_from_dict(item) for item in self._read_json(self.seen_hosts_path)]
        return sorted(entries, key=lambda entry: entry.last_seen, reverse=True)

    def save_seen(
        self,
        index: int,
        *,
        name: str,
        profile: str | None = None,
        tags: builtins.list[str] | None = None,
        notes: str | None = None,
    ) -> HostEntry:
        seen = self.list_seen()
        if index < 1 or index > len(seen):
            raise IndexError(f"recent host id out of range: {index}")
        selected = seen[index - 1]
        entry = HostEntry(
            name=name,
            host=selected.host,
            port=selected.port or _default_port(selected.protocol),
            protocol=selected.protocol,
            username=selected.username,
            profile=profile,
            tags=tags or [],
            notes=notes,
        )
        self.add(entry)
        return entry

    def _read_json(self, path: Path) -> builtins.list[dict[str, Any]]:
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise TypeError(f"invalid maxconn data file: {path}")
        return data

    def _write_hosts(self, entries: builtins.list[HostEntry]) -> None:
        self._write_json(self.hosts_path, [_host_to_dict(entry) for entry in entries])

    def _write_seen(self, entries: builtins.list[SeenHostEntry]) -> None:
        self._write_json(self.seen_hosts_path, [asdict(entry) for entry in entries])

    def _write_json(self, path: Path, data: builtins.list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def _host_from_dict(self, data: dict[str, Any]) -> HostEntry:
        return HostEntry(
            name=str(data["name"]),
            host=str(data["host"]),
            port=int(data["port"]),
            protocol=str(data["protocol"]),
            username=_optional_str(data.get("username")),
            profile=_optional_str(data.get("profile")),
            tags=[str(tag) for tag in data.get("tags", [])],
            notes=_optional_str(data.get("notes")),
            password=_optional_str(data.get("password")),
        )

    def _seen_from_dict(self, data: dict[str, Any]) -> SeenHostEntry:
        raw_port = data.get("port")
        return SeenHostEntry(
            host=str(data["host"]),
            protocol=str(data["protocol"]),
            port=None if raw_port is None else int(raw_port),
            username=_optional_str(data.get("username")),
            first_seen=str(data["first_seen"]),
            last_seen=str(data["last_seen"]),
            count=int(data["count"]),
        )


def format_hosts_table(entries: list[HostEntry]) -> str:
    rows = [
        [
            entry.name,
            entry.host,
            str(entry.port),
            entry.protocol,
            entry.username or "",
            entry.profile or "",
            ",".join(entry.tags or []),
            "yes" if entry.password else "no",
        ]
        for entry in entries
    ]
    return _format_table(["NAME", "HOST/IP", "PORT", "PROTOCOL", "USER", "PROFILE", "TAGS", "PASSWORD"], rows)


def format_seen_hosts_table(entries: list[SeenHostEntry]) -> str:
    rows = [
        [
            str(index),
            entry.host,
            "" if entry.port is None else str(entry.port),
            entry.protocol,
            entry.username or "",
            entry.last_seen,
            str(entry.count),
        ]
        for index, entry in enumerate(entries, start=1)
    ]
    return _format_table(["ID", "HOST/IP", "PORT", "PROTOCOL", "USER", "LAST_SEEN", "COUNT"], rows)


def parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


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


def _host_to_dict(entry: HostEntry) -> dict[str, Any]:
    data = asdict(entry)
    data["tags"] = list(entry.tags or [])
    return data


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _default_port(protocol: str) -> int:
    if protocol.lower() == "telnet":
        return 23
    return 22


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
