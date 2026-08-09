"""maxconn - SSH and Telnet client built from scratch."""

from __future__ import annotations

from maxconn.exceptions import (
    AuthenticationError,
    ChannelError,
    ConnectionTimeoutError,
    MaxConnError,
    ProtocolError,
)
from maxconn.transport.base import Connection
from maxconn.transport.telnet.transport import TelnetTransport

__all__ = [
    "AuthenticationError",
    "ChannelError",
    "Connection",
    "ConnectionTimeoutError",
    "MaxConnError",
    "ProtocolError",
    "connect",
]

_DEFAULT_PORTS = {"telnet": 23}


def connect(
    host: str,
    *,
    protocol: str,
    username: str,
    password: str | None = None,
    port: int | None = None,
    timeout: float = 10.0,
) -> Connection:
    if protocol == "telnet":
        transport = TelnetTransport()
    else:
        raise ValueError(
            f"Unsupported protocol: {protocol!r}. Supported: 'telnet' ('ssh' coming in a future release)"
        )

    resolved_port = port if port is not None else _DEFAULT_PORTS[protocol]
    transport.connect(host, resolved_port, timeout)
    transport.authenticate(username, password=password)
    return Connection(transport)
