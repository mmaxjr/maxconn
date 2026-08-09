"""SSH user authentication (RFC 4252): the ssh-userauth service request,
plus the "password" and "publickey" authentication methods."""

from __future__ import annotations

from maxconn.exceptions import AuthenticationError, ProtocolError
from maxconn.transport.ssh import messages
from maxconn.transport.ssh.negotiate import EncryptedSession
from maxconn.transport.ssh.wire import Reader, encode_string

_MAX_BANNERS = 10


def request_userauth_service(session: EncryptedSession) -> None:
    request = bytes([messages.SSH_MSG_SERVICE_REQUEST]) + encode_string(b"ssh-userauth")
    session.send_message(request)

    reader = Reader(session.recv_message())
    msg_type = reader.read_byte()
    if msg_type != messages.SSH_MSG_SERVICE_ACCEPT:
        raise ProtocolError(f"Expected SSH_MSG_SERVICE_ACCEPT ({messages.SSH_MSG_SERVICE_ACCEPT}), got {msg_type}")
    service_name = reader.read_string()
    if service_name != b"ssh-userauth":
        raise ProtocolError(f"Unexpected service accepted: {service_name!r}")


def _read_until_auth_result(session: EncryptedSession) -> bytes:
    """SSH_MSG_USERAUTH_BANNER may arrive before the real result; skip it."""
    for _ in range(_MAX_BANNERS):
        payload = session.recv_message()
        if payload and payload[0] == messages.SSH_MSG_USERAUTH_BANNER:
            continue
        return payload
    raise ProtocolError("Too many SSH_MSG_USERAUTH_BANNER messages without an auth result")


def authenticate_password(session: EncryptedSession, username: str, password: str) -> None:
    request = (
        bytes([messages.SSH_MSG_USERAUTH_REQUEST])
        + encode_string(username.encode("utf-8"))
        + encode_string(b"ssh-connection")
        + encode_string(b"password")
        + bytes([0])  # FALSE: this is not a change-password request
        + encode_string(password.encode("utf-8"))
    )
    session.send_message(request)

    payload = _read_until_auth_result(session)
    reader = Reader(payload)
    msg_type = reader.read_byte()
    if msg_type == messages.SSH_MSG_USERAUTH_SUCCESS:
        return
    if msg_type == messages.SSH_MSG_USERAUTH_FAILURE:
        raise AuthenticationError(f"SSH password authentication failed for user {username!r}")
    raise ProtocolError(f"Unexpected message during password authentication: {msg_type}")
