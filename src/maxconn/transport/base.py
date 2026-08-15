"""Transport abstraction shared by SSH and Telnet implementations."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from maxconn._redact import redact as _redact
from maxconn.automation import ExpectSession, PromptProfile
from maxconn.exceptions import ConnectionTimeoutError

_AUDIT_LOG = logging.getLogger("maxconn.audit")
# Python socket semantics treat timeout=None as "block forever," not "use a
# sensible default." Connection.recv()/.send() are documented as public
# low-level escape hatches, so a caller that omits the argument must not
# silently hang forever against a device that stops responding.
DEFAULT_RECV_TIMEOUT = 30.0


class Transport(ABC):
    @abstractmethod
    def connect(self, host: str, port: int, timeout: float) -> None: ...

    @abstractmethod
    def authenticate(
        self,
        username: str,
        password: str | None = None,
        pkey: object | None = None,
        timeout: float | None = None,
    ) -> None: ...
    # `pkey`'s concrete type is transport-specific (e.g. SSHTransport
    # expects a cryptography RSAPrivateKey); transports that don't support
    # key-based auth raise AuthenticationError when it's passed.

    @abstractmethod
    def send(self, data: bytes | str) -> None: ...

    @abstractmethod
    def recv(self, timeout: float = DEFAULT_RECV_TIMEOUT) -> bytes: ...

    @abstractmethod
    def close(self) -> None: ...


def read_until(transport: Transport, markers: tuple[str, ...], timeout: float) -> str:
    deadline = time.monotonic() + timeout
    buffer = ""
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        chunk = transport.recv(timeout=max(remaining, 0.01))
        buffer += chunk.decode(errors="replace")
        if any(marker.lower() in buffer.lower() for marker in markers):
            return buffer
    raise ConnectionTimeoutError(f"Timed out waiting for markers {markers!r}; got: {buffer!r}")


@dataclass(frozen=True)
class CommandResult:
    command: str
    text: str
    bytes: bytes
    elapsed: float
    exit_status: int | None = None

    @property
    def ok(self) -> bool:
        return self.exit_status in (None, 0)


class Connection:
    def __init__(
        self,
        transport: Transport,
        *,
        host: str | None = None,
        protocol: str | None = None,
        command_timeout: float = 5.0,
        prompt_timeout: float = 10.0,
        prompt_profile: PromptProfile = PromptProfile.GENERIC,
    ) -> None:
        self._transport = transport
        self.host = host
        self.protocol = protocol
        self.command_timeout = command_timeout
        self.prompt_timeout = prompt_timeout
        self.prompt_profile = prompt_profile

    def send_command(self, command: str, *, read_timeout: float = 5.0) -> str:
        self._transport.send(command + "\n")
        deadline = time.monotonic() + read_timeout
        buffer = ""
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                chunk = self._transport.recv(timeout=max(remaining, 0.01))
            except ConnectionTimeoutError:
                break
            buffer += chunk.decode(errors="replace")
        return buffer

    def run(
        self,
        command: str,
        *,
        prompt_markers: tuple[str, ...] | None = None,
        timeout: float | None = None,
        strip_echo: bool = True,
        pagination_markers: tuple[str, ...] = ("--More--",),
    ) -> CommandResult:
        start = time.monotonic()
        resolved_timeout = timeout if timeout is not None else self.command_timeout
        resolved_markers = prompt_markers if prompt_markers is not None else self.prompt_profile.markers
        expect = ExpectSession(
            self,
            prompt_markers=resolved_markers,
            pagination_markers=pagination_markers,
        )

        text = expect.run(command, timeout=resolved_timeout, strip_echo=strip_echo)
        elapsed = time.monotonic() - start
        result = CommandResult(
            command=command,
            text=text,
            bytes=text.encode(),
            elapsed=elapsed,
        )
        _AUDIT_LOG.info(
            "command completed host=%s protocol=%s command=%r elapsed=%.3f ok=%s",
            self.host,
            self.protocol,
            _redact(command),
            elapsed,
            result.ok,
        )
        return result

    def send(self, data: bytes | str) -> None:
        self._transport.send(data)

    def recv(self, timeout: float = DEFAULT_RECV_TIMEOUT) -> bytes:
        return self._transport.recv(timeout=timeout)

    def read_until(self, marker: str, timeout: float = 10.0) -> str:
        return read_until(self._transport, (marker,), timeout)

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> Connection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
