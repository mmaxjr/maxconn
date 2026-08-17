"""maxconn - SSH and Telnet client built from scratch."""

from __future__ import annotations

__version__ = "0.3.0"

from maxconn.exceptions import (
    AuthenticationError,
    ChannelError,
    ConnectionTimeoutError,
    MaxConnError,
    ProtocolError,
)
from maxconn.net import (
    DEFAULT_DISCOVER_PORTS,
    DiscoverHost,
    MTRResult,
    PingResult,
    ScanResult,
    TraceRouteResult,
    discover,
    mtr,
    ping,
    scan,
    traceroute,
)
from maxconn.sessions import SessionManager
from maxconn.transport.base import CommandResult, Connection, Transport

__all__ = [
    "DEFAULT_DISCOVER_PORTS",
    "AuthenticationError",
    "ChannelError",
    "CommandResult",
    "Connection",
    "ConnectionTimeoutError",
    "DiscoverHost",
    "MTRResult",
    "MaxConnError",
    "PingResult",
    "ProtocolError",
    "ScanResult",
    "SessionManager",
    "TraceRouteResult",
    "__version__",
    "connect",
    "connect_sftp",
    "discover",
    "mtr",
    "ping",
    "scan",
    "traceroute",
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
    connect_timeout: float | None = None,
    auth_timeout: float | None = None,
    command_timeout: float = 5.0,
    prompt_timeout: float = 10.0,
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
    resolved_connect_timeout = connect_timeout if connect_timeout is not None else timeout
    resolved_auth_timeout = auth_timeout if auth_timeout is not None else timeout
    transport.connect(host, resolved_port, resolved_connect_timeout)
    try:
        transport.authenticate(username, password=password, pkey=pkey, timeout=resolved_auth_timeout)
    except Exception:
        transport.close()
        raise
    return Connection(
        transport,
        host=host,
        protocol=protocol,
        command_timeout=command_timeout,
        prompt_timeout=prompt_timeout,
    )


def connect_sftp(
    host: str,
    *,
    username: str,
    password: str | None = None,
    pkey: object | None = None,
    port: int = 22,
    timeout: float = 10.0,
):
    from maxconn.protocol.sftp import connect_sftp as _connect_sftp

    return _connect_sftp(
        host,
        username=username,
        password=password,
        pkey=pkey,
        port=port,
        timeout=timeout,
    )
