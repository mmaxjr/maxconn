"""Transport abstraction shared by SSH and Telnet implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Transport(ABC):
    @abstractmethod
    def connect(self, host: str, port: int, timeout: float) -> None: ...

    @abstractmethod
    def authenticate(
        self,
        username: str,
        password: str | None = None,
        pkey: bytes | None = None,
    ) -> None: ...

    @abstractmethod
    def send(self, data: bytes | str) -> None: ...

    @abstractmethod
    def recv(self, timeout: float | None = None) -> bytes: ...

    @abstractmethod
    def close(self) -> None: ...
