"""maxconn - SSH and Telnet client built from scratch."""

from __future__ import annotations

from maxconn.exceptions import (
    AuthenticationError,
    ChannelError,
    ConnectionTimeoutError,
    MaxConnError,
    ProtocolError,
)
from maxconn.transport.base import Connection, Transport

__all__ = [
    "AuthenticationError",
    "ChannelError",
    "Connection",
    "ConnectionTimeoutError",
    "MaxConnError",
    "ProtocolError",
    "connect",
]

_DEFAULT_PORTS = {"telnet": 23, "ssh": 22}


def connect(
    host: str,
    *,
    protocol: str,
    username: str,
    password: str | None = None,
    pkey: object | None = None,
    port: int | None = None,
    timeout: float = 10.0,
) -> Connection:
    # Imported per-protocol, not at module load, so using one transport
    # never pulls in the other's dependencies (see the "import only what
    # you use" rule in the project brief).
    transport: Transport
    if protocol == "telnet":
        from maxconn.transport.telnet.transport import TelnetTransport

        transport = TelnetTransport()
    elif protocol == "ssh":
        from maxconn.transport.ssh.transport import SSHTransport

        transport = SSHTransport()
    else:
        raise ValueError(f"Unsupported protocol: {protocol!r}. Supported: 'telnet', 'ssh'")

    resolved_port = port if port is not None else _DEFAULT_PORTS[protocol]
    transport.connect(host, resolved_port, timeout)
    transport.authenticate(username, password=password, pkey=pkey)
    return Connection(transport)
