"""A local SSH server used only by the test suite, powered by `paramiko`.

This is a TEST-ONLY dependency: it exists to validate maxconn's from-scratch
SSHTransport against a real, independent SSH implementation. `paramiko` is
never imported by the `maxconn` package itself.
"""

from __future__ import annotations

import socket
import threading
from dataclasses import dataclass

import paramiko


class _ServerInterface(paramiko.ServerInterface):
    def __init__(self, username: str, password: str, authorized_key: paramiko.PKey) -> None:
        self.username = username
        self.password = password
        self.authorized_key = authorized_key

    def check_channel_request(self, kind: str, chanid: int) -> int:
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def get_allowed_auths(self, username: str) -> str:
        return "password,publickey"

    def check_auth_password(self, username: str, password: str) -> int:
        if username == self.username and password == self.password:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_auth_publickey(self, username: str, key: paramiko.PKey) -> int:
        if username == self.username and key.get_fingerprint() == self.authorized_key.get_fingerprint():
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_channel_shell_request(self, channel: paramiko.Channel) -> bool:
        threading.Thread(target=_run_echo_shell, args=(channel,), daemon=True).start()
        return True

    def check_channel_pty_request(self, *args: object, **kwargs: object) -> bool:
        return True

    def check_channel_exec_request(self, channel: paramiko.Channel, command: bytes) -> bool:
        threading.Thread(target=_run_exec, args=(channel, command), daemon=True).start()
        return True


def _run_exec(channel: paramiko.Channel, command: bytes) -> None:
    cmd = command.decode(errors="replace") if isinstance(command, bytes) else command
    channel.send(f"echo:{cmd}\n".encode())
    channel.send_exit_status(0)
    channel.close()


def _run_echo_shell(channel: paramiko.Channel) -> None:
    channel.send(b"Welcome\ndevice> ")
    buffer = bytearray()
    while True:
        try:
            chunk = channel.recv(1)
        except OSError:
            return
        if not chunk:
            return
        if chunk == b"\n":
            line = bytes(buffer).decode(errors="replace").rstrip("\r")
            buffer.clear()
            if line == "exit":
                channel.close()
                return
            channel.send(f"echo:{line}\ndevice> ".encode())
        else:
            buffer.extend(chunk)


def _serve_client(
    conn: socket.socket, username: str, password: str, host_key: paramiko.PKey, client_key: paramiko.PKey
) -> None:
    transport = paramiko.Transport(conn)
    transport.add_server_key(host_key)
    server = _ServerInterface(username, password, client_key)
    try:
        transport.start_server(server=server)
    except (paramiko.SSHException, OSError):
        return

    channel = transport.accept(20)
    if channel is None:
        transport.close()
        return
    while transport.is_active():
        threading.Event().wait(0.05)


@dataclass
class SSHServerHandle:
    host: str
    port: int
    username: str
    password: str
    host_key: paramiko.PKey
    client_key: paramiko.PKey
    thread: threading.Thread
    _server_socket: socket.socket

    def stop(self) -> None:
        self._server_socket.close()
        self.thread.join(timeout=2.0)


def start_ssh_server(username: str = "admin", password: str = "secret") -> SSHServerHandle:
    host_key = paramiko.RSAKey.generate(2048)
    client_key = paramiko.RSAKey.generate(2048)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(5)
    host, port = server_socket.getsockname()

    def _serve() -> None:
        while True:
            try:
                conn, _ = server_socket.accept()
            except OSError:
                return
            threading.Thread(
                target=_serve_client, args=(conn, username, password, host_key, client_key), daemon=True
            ).start()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()

    return SSHServerHandle(
        host=host,
        port=port,
        username=username,
        password=password,
        host_key=host_key,
        client_key=client_key,
        thread=thread,
        _server_socket=server_socket,
    )
