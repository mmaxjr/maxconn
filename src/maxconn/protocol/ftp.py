from __future__ import annotations

import re
import socket
from dataclasses import dataclass


@dataclass(frozen=True)
class FTPReply:
    code: int
    message: str


class FTPClient:
    def __init__(self, sock: socket.socket, *, timeout: float = 10.0) -> None:
        self._sock = sock
        self._file = sock.makefile("r", encoding="utf-8", newline="\r\n")
        self.timeout = timeout

    @classmethod
    def connect(
        cls,
        host: str,
        *,
        port: int = 21,
        username: str = "anonymous",
        password: str = "anonymous@",
        timeout: float = 10.0,
    ) -> FTPClient:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.settimeout(timeout)
        client = cls(sock, timeout=timeout)
        try:
            client._expect(220)
            client._login(username, password)
            client._command("TYPE I", expected=200)
        except Exception:
            client.close()
            raise
        return client

    def __enter__(self) -> FTPClient:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def list(self, path: str = "") -> str:
        data_sock = self._open_passive_data_socket()
        command = f"LIST {path}".strip()
        self._command(command, expected=150)
        data = _read_all(data_sock)
        data_sock.close()
        self._expect(226)
        return data.decode("utf-8", errors="replace")

    def download(self, path: str) -> bytes:
        data_sock = self._open_passive_data_socket()
        self._command(f"RETR {path}", expected=150)
        data = _read_all(data_sock)
        data_sock.close()
        self._expect(226)
        return data

    def close(self) -> None:
        try:
            self._command("QUIT", expected=221)
        except (OSError, ValueError):
            # close() must be a safe best-effort cleanup call - a server
            # that drops the connection or replies unexpectedly to QUIT
            # (e.g. right after rejecting a login) must not stop the
            # socket itself from being closed below, and must not mask
            # whatever exception the caller is already propagating.
            pass
        finally:
            self._file.close()
            self._sock.close()

    def _login(self, username: str, password: str) -> None:
        reply = self._command(f"USER {username}", expected={230, 331})
        if reply.code == 331:
            self._command(f"PASS {password}", expected=230)

    def _open_passive_data_socket(self) -> socket.socket:
        reply = self._command("PASV", expected=227)
        host, port = _parse_pasv(reply.message)
        data_sock = socket.create_connection((host, port), timeout=self.timeout)
        data_sock.settimeout(self.timeout)
        return data_sock

    def _command(self, command: str, *, expected: int | set[int]) -> FTPReply:
        self._sock.sendall((command + "\r\n").encode())
        return self._expect(expected)

    def _expect(self, expected: int | set[int]) -> FTPReply:
        reply = self._read_reply()
        expected_codes = {expected} if isinstance(expected, int) else expected
        if reply.code not in expected_codes:
            raise ValueError(f"unexpected FTP reply {reply.code}: {reply.message}")
        return reply

    def _read_reply(self) -> FTPReply:
        line = self._file.readline()
        if not line:
            raise ValueError("FTP server closed the connection")
        code = int(line[:3])
        message = line[4:].strip()
        return FTPReply(code=code, message=message)


def _parse_pasv(message: str) -> tuple[str, int]:
    match = re.search(r"\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)", message)
    if not match:
        raise ValueError(f"invalid PASV reply: {message}")
    h1, h2, h3, h4, p1, p2 = (int(part) for part in match.groups())
    return f"{h1}.{h2}.{h3}.{h4}", p1 * 256 + p2


def _read_all(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    with sock:
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks)
