from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import maxconn


@dataclass
class ManagedSession:
    name: str
    host: str
    connection: Any


class SessionManager:
    def __init__(self, *, defaults: dict[str, Any] | None = None) -> None:
        self.defaults = defaults or {}
        self._sessions: dict[str, ManagedSession] = {}

    def add(self, name: str, connection: Any, *, host: str) -> Any:
        existing = self._sessions.get(name)
        if existing is not None:
            existing.connection.close()
        self._sessions[name] = ManagedSession(name=name, host=host, connection=connection)
        return connection

    def connect(self, name: str, host: str, **kwargs: Any) -> Any:
        options = {**self.defaults, **kwargs}
        connection = maxconn.connect(host, **options)
        return self.add(name, connection, host=host)

    def get(self, name: str) -> Any:
        return self._sessions[name].connection

    def names(self) -> list[str]:
        return list(self._sessions)

    def close(self, name: str) -> None:
        session = self._sessions.pop(name)
        session.connection.close()

    def close_all(self) -> None:
        first_error: Exception | None = None
        for name in list(self._sessions):
            try:
                self.close(name)
            except Exception as exc:  # noqa: BLE001 - re-raised below, must not skip remaining closes
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error
