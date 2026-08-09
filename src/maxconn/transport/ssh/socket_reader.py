"""Buffered reader over a raw socket, shared by every phase of the SSH
transport (version banner, plaintext packets, encrypted packets)."""

from __future__ import annotations

import socket

from maxconn.exceptions import ConnectionTimeoutError, ProtocolError


class SocketReader:
    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._buffer = bytearray()

    def read_exact(self, n: int) -> bytes:
        while len(self._buffer) < n:
            self._fill(max(4096, n - len(self._buffer)))
        data = bytes(self._buffer[:n])
        del self._buffer[:n]
        return data

    def read_line(self) -> bytes:
        while b"\n" not in self._buffer:
            self._fill(4096)
        idx = self._buffer.index(b"\n")
        line = bytes(self._buffer[: idx + 1])
        del self._buffer[: idx + 1]
        return line.rstrip(b"\r\n")

    def _fill(self, size: int) -> None:
        try:
            chunk = self._sock.recv(size)
        except TimeoutError as exc:
            raise ConnectionTimeoutError("Timed out waiting for SSH data") from exc
        except OSError as exc:
            raise ProtocolError(f"Socket error while receiving SSH data: {exc}") from exc
        if not chunk:
            raise ProtocolError("Connection closed by remote host")
        self._buffer.extend(chunk)
