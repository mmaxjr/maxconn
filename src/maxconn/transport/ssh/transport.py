"""SSHTransport: ties the handshake, authentication, and channel modules
together behind the shared `Transport` interface."""

from __future__ import annotations

import socket

from cryptography.hazmat.primitives.asymmetric import rsa

from maxconn.exceptions import AuthenticationError, ConnectionTimeoutError, ProtocolError
from maxconn.transport.base import Transport
from maxconn.transport.ssh.auth import (
    authenticate_password,
    authenticate_publickey,
    request_userauth_service,
)
from maxconn.transport.ssh.channel import SSHChannel, open_session_channel
from maxconn.transport.ssh.negotiate import EncryptedSession, establish_encrypted_session


class SSHTransport(Transport):
    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._session: EncryptedSession | None = None
        self._channel: SSHChannel | None = None

    def connect(self, host: str, port: int, timeout: float) -> None:
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
        except OSError as exc:
            raise ConnectionTimeoutError(f"Could not connect to {host}:{port}: {exc}") from exc
        self._sock = sock
        try:
            self._session = establish_encrypted_session(sock)
        except Exception:
            sock.close()
            self._sock = None
            raise

    def authenticate(
        self,
        username: str,
        password: str | None = None,
        pkey: object | None = None,
        timeout: float | None = None,
    ) -> None:
        if self._session is None:
            raise ProtocolError("Cannot authenticate: not connected")
        if self._sock is not None and timeout is not None:
            self._sock.settimeout(timeout)

        request_userauth_service(self._session)

        if pkey is not None:
            if not isinstance(pkey, rsa.RSAPrivateKey):
                raise AuthenticationError(
                    "maxconn's SSH public-key auth expects a cryptography RSAPrivateKey for `pkey` in v0.1"
                )
            authenticate_publickey(self._session, username, pkey)
        elif password is not None:
            authenticate_password(self._session, username, password)
        else:
            raise AuthenticationError("SSH authentication requires a password or a private key")

        self._channel = open_session_channel(self._session)
        self._channel.request_shell()

    def send(self, data: bytes | str) -> None:
        if self._channel is None:
            raise ProtocolError("Cannot send: not authenticated")
        payload = data.encode() if isinstance(data, str) else data
        self._channel.send_data(payload)

    def recv(self, timeout: float | None = None) -> bytes:
        if self._channel is None:
            raise ProtocolError("Cannot recv: not authenticated")
        if self._sock is not None:
            self._sock.settimeout(timeout)
        return self._channel.recv_data()

    def close(self) -> None:
        if self._channel is not None:
            self._channel.close()
            self._channel = None
        if self._sock is not None:
            self._sock.close()
            self._sock = None
