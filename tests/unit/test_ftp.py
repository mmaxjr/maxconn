from __future__ import annotations

import socket
import threading

import pytest

from maxconn.protocol.ftp import FTPClient


class _FTPServer:
    def __init__(self, *, reject_login: bool = False) -> None:
        self.control = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.control.bind(("127.0.0.1", 0))
        self.control.listen(1)
        self.port = self.control.getsockname()[1]
        self.reject_login = reject_login
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def _serve(self) -> None:
        conn, _addr = self.control.accept()
        with conn:
            self._send(conn, "220 maxconn test ftp")
            data_listener: socket.socket | None = None
            while True:
                line = self._readline(conn)
                command, _, arg = line.partition(" ")
                if command == "USER":
                    self._send(conn, "331 password required")
                elif command == "PASS":
                    if self.reject_login:
                        self._send(conn, "530 login incorrect")
                        continue
                    self._send(conn, "230 logged in")
                elif command == "TYPE":
                    self._send(conn, "200 type set")
                elif command == "PASV":
                    data_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    data_listener.bind(("127.0.0.1", 0))
                    data_listener.listen(1)
                    port = data_listener.getsockname()[1]
                    p1, p2 = divmod(port, 256)
                    self._send(conn, f"227 entering passive mode (127,0,0,1,{p1},{p2})")
                elif command == "LIST":
                    assert data_listener is not None
                    self._send(conn, "150 opening data")
                    data_conn, _data_addr = data_listener.accept()
                    with data_conn:
                        data_conn.sendall(b"-rw-r--r-- 1 user group 5 Jan 01 file.txt\r\n")
                    data_listener.close()
                    self._send(conn, "226 transfer complete")
                elif command == "RETR":
                    assert data_listener is not None
                    self._send(conn, "150 opening data")
                    data_conn, _data_addr = data_listener.accept()
                    with data_conn:
                        data_conn.sendall(f"contents of {arg}".encode())
                    data_listener.close()
                    self._send(conn, "226 transfer complete")
                elif command == "QUIT":
                    self._send(conn, "221 bye")
                    break

    def _send(self, conn: socket.socket, message: str) -> None:
        conn.sendall((message + "\r\n").encode())

    def _readline(self, conn: socket.socket) -> str:
        data = bytearray()
        while not data.endswith(b"\r\n"):
            data.extend(conn.recv(1))
        return data.decode().strip()


def test_ftp_client_logs_in_lists_and_downloads_file():
    server = _FTPServer()
    server.start()

    with FTPClient.connect(
        "127.0.0.1",
        port=server.port,
        username="user",
        password="secret",
        timeout=1.0,
    ) as ftp:
        listing = ftp.list()
        data = ftp.download("file.txt")

    assert "file.txt" in listing
    assert data == b"contents of file.txt"


def test_ftp_client_connect_closes_the_socket_when_login_fails(monkeypatch):
    # Regression: connect() opened the control socket before running the
    # banner/login sequence, but never closed it if that sequence raised -
    # a rejected login leaked the socket.
    server = _FTPServer(reject_login=True)
    server.start()

    created_sockets = []
    real_create_connection = socket.create_connection

    def capturing_create_connection(*args, **kwargs):
        sock = real_create_connection(*args, **kwargs)
        created_sockets.append(sock)
        return sock

    monkeypatch.setattr(socket, "create_connection", capturing_create_connection)

    with pytest.raises(ValueError, match="530"):
        FTPClient.connect(
            "127.0.0.1",
            port=server.port,
            username="user",
            password="wrong",
            timeout=1.0,
        )

    assert len(created_sockets) == 1
    assert created_sockets[0].fileno() == -1  # closed sockets report fileno() == -1
