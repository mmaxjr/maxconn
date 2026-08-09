"""Telnet transport built directly on top of `socket` (no `telnetlib`)."""

from __future__ import annotations

import socket
import time

from maxconn.exceptions import AuthenticationError, ConnectionTimeoutError, ProtocolError
from maxconn.transport.base import Transport
from maxconn.transport.telnet.negotiation import TelnetNegotiator


class TelnetTransport(Transport):
    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._negotiator = TelnetNegotiator()

    def connect(self, host: str, port: int, timeout: float) -> None:
        try:
            self._sock = socket.create_connection((host, port), timeout=timeout)
        except OSError as exc:
            raise ConnectionTimeoutError(f"Could not connect to {host}:{port}: {exc}") from exc

    def authenticate(
        self,
        username: str,
        password: str | None = None,
        pkey: object | None = None,
    ) -> None:
        if pkey is not None:
            raise AuthenticationError("Telnet does not support public-key authentication")

        self._read_until(("login:", "username:"), timeout=10.0)
        self.send(username + "\n")

        if password is not None:
            self._read_until(("password:",), timeout=10.0)
            self.send(password + "\n")

        reply = self._read_until(("welcome", "incorrect", "failed", ">", "#"), timeout=10.0)
        if "incorrect" in reply.lower() or "failed" in reply.lower():
            raise AuthenticationError(f"Telnet authentication failed for user {username!r}")

    def _read_until(self, markers: tuple[str, ...], timeout: float) -> str:
        deadline = time.monotonic() + timeout
        buffer = ""
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            chunk = self.recv(timeout=max(remaining, 0.01))
            buffer += chunk.decode(errors="replace")
            if any(marker in buffer.lower() for marker in markers):
                return buffer
        raise ConnectionTimeoutError(f"Timed out waiting for {markers!r}; got: {buffer!r}")

    def send(self, data: bytes | str) -> None:
        if self._sock is None:
            raise ProtocolError("Cannot send: not connected")
        payload = data.encode() if isinstance(data, str) else data
        self._sock.sendall(payload)

    def recv(self, timeout: float | None = None) -> bytes:
        if self._sock is None:
            raise ProtocolError("Cannot recv: not connected")
        self._sock.settimeout(timeout)
        try:
            raw = self._sock.recv(4096)
        except TimeoutError as exc:
            raise ConnectionTimeoutError("Timed out waiting for data") from exc
        except OSError as exc:
            raise ProtocolError(f"Socket error while receiving data: {exc}") from exc

        plain, response = self._negotiator.feed(raw)
        if response:
            self._sock.sendall(response)
        return plain

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None
