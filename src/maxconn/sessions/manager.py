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
        for name in list(self._sessions):
            self.close(name)
