"""SSH protocol version exchange (RFC 4253 section 4.2)."""

from __future__ import annotations

import socket

from maxconn.exceptions import ProtocolError
from maxconn.transport.ssh.socket_reader import SocketReader

CLIENT_ID = "SSH-2.0-maxconn_0.1"
_MAX_PREAMBLE_LINES = 50  # tolerate a handful of non-SSH lines before the banner


def send_version(sock: socket.socket) -> bytes:
    banner = f"{CLIENT_ID}\r\n".encode("ascii")
    sock.sendall(banner)
    return CLIENT_ID.encode("ascii")


def recv_version(reader: SocketReader) -> bytes:
    for _ in range(_MAX_PREAMBLE_LINES):
        line = reader.read_line()
        if line.startswith(b"SSH-"):
            return line
    raise ProtocolError("No SSH identification string received from remote host")
