"""A minimal Telnet server used only by the test suite to validate
TelnetTransport against a real socket peer. Not shipped in the package."""

from __future__ import annotations

import socket
import threading
from dataclasses import dataclass

IAC = 255
WILL = 251
ECHO = 1
SUPPRESS_GO_AHEAD = 3


@dataclass
class TelnetServerHandle:
    host: str
    port: int
    username: str
    password: str
    thread: threading.Thread
    _server_socket: socket.socket

    def stop(self) -> None:
        self._server_socket.close()
        self.thread.join(timeout=2.0)


def _handle_client(conn: socket.socket, username: str, password: str) -> None:
    with conn:
        conn.sendall(bytes([IAC, WILL, ECHO]))
        conn.sendall(bytes([IAC, WILL, SUPPRESS_GO_AHEAD]))
        conn.sendall(b"login: ")
        got_username = _read_line(conn)
        conn.sendall(b"Password: ")
        got_password = _read_line(conn)

        if got_username != username or got_password != password:
            conn.sendall(b"Login incorrect\n")
            return

        conn.sendall(b"Welcome\ndevice> ")
        while True:
            line = _read_line(conn)
            if line is None or line == "exit":
                return
            conn.sendall(f"echo:{line}\ndevice> ".encode())


def _read_line(conn: socket.socket) -> str | None:
    buffer = bytearray()
    while True:
        chunk = conn.recv(1)
        if not chunk:
            return None
        if chunk == b"\n":
            return bytes(buffer).decode(errors="replace").rstrip("\r")
        buffer.extend(chunk)


def start_telnet_server(username: str = "admin", password: str = "secret") -> TelnetServerHandle:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    host, port = server_socket.getsockname()

    def _serve() -> None:
        while True:
            try:
                conn, _ = server_socket.accept()
            except OSError:
                return
            threading.Thread(
                target=_handle_client, args=(conn, username, password), daemon=True
            ).start()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()

    return TelnetServerHandle(
        host=host,
        port=port,
        username=username,
        password=password,
        thread=thread,
        _server_socket=server_socket,
    )
