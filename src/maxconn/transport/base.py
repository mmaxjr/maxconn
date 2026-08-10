"""Transport abstraction shared by SSH and Telnet implementations."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

from maxconn.exceptions import ConnectionTimeoutError


class Transport(ABC):
    @abstractmethod
    def connect(self, host: str, port: int, timeout: float) -> None: ...

    @abstractmethod
    def authenticate(
        self,
        username: str,
        password: str | None = None,
        pkey: object | None = None,
    ) -> None: ...
    # `pkey`'s concrete type is transport-specific (e.g. SSHTransport
    # expects a cryptography RSAPrivateKey); transports that don't support
    # key-based auth raise AuthenticationError when it's passed.

    @abstractmethod
    def send(self, data: bytes | str) -> None: ...

    @abstractmethod
    def recv(self, timeout: float | None = None) -> bytes: ...

    @abstractmethod
    def close(self) -> None: ...


def read_until(transport: Transport, markers: tuple[str, ...], timeout: float) -> str:
    deadline = time.monotonic() + timeout
    buffer = ""
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        chunk = transport.recv(timeout=max(remaining, 0.01))
        buffer += chunk.decode(errors="replace")
        if any(marker.lower() in buffer.lower() for marker in markers):
            return buffer
    raise ConnectionTimeoutError(f"Timed out waiting for markers {markers!r}; got: {buffer!r}")


class Connection:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def send_command(self, command: str, *, read_timeout: float = 5.0) -> str:
        self._transport.send(command + "\n")
        deadline = time.monotonic() + read_timeout
        buffer = ""
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                chunk = self._transport.recv(timeout=max(remaining, 0.01))
            except ConnectionTimeoutError:
                break
            buffer += chunk.decode(errors="replace")
        return buffer

    def send(self, data: bytes | str) -> None:
        self._transport.send(data)

    def recv(self, timeout: float | None = None) -> bytes:
        return self._transport.recv(timeout=timeout)

    def read_until(self, marker: str, timeout: float = 10.0) -> str:
        return read_until(self._transport, (marker,), timeout)

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> Connection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
