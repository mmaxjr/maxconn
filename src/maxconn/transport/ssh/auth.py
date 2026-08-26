"""SSH user authentication (RFC 4252): the ssh-userauth service request,
plus the "password" and "publickey" authentication methods."""

from __future__ import annotations

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from maxconn.exceptions import AuthenticationError, ProtocolError
from maxconn.transport.ssh import messages
from maxconn.transport.ssh.negotiate import EncryptedSession
from maxconn.transport.ssh.wire import Reader, encode_mpint, encode_string

_MAX_BANNERS = 10
_PUBKEY_ALGORITHM = "rsa-sha2-256"


def build_rsa_public_key_blob(public_key: rsa.RSAPublicKey) -> bytes:
    numbers = public_key.public_numbers()
    return encode_string(b"ssh-rsa") + encode_mpint(numbers.e) + encode_mpint(numbers.n)


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
    """SSH_MSG_USERAUTH_BANNER may arrive before the real result."""
    for _ in range(_MAX_BANNERS):
        payload = session.recv_message()
        if payload and payload[0] == messages.SSH_MSG_USERAUTH_BANNER:
            reader = Reader(payload)
            reader.read_byte()
            message = reader.read_string()
            language = reader.read_string()
            session.pending_terminal_output.append(
                b"Pre-authentication banner message from server:\r\n"
                + message.replace(b"\n", b"\r\n")
                + b"\r\nEnd of banner message from server\r\n"
            )
            if language:
                session.pending_terminal_output.append(b"Banner language: " + language + b"\r\n")
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


def authenticate_publickey(session: EncryptedSession, username: str, private_key: rsa.RSAPrivateKey) -> None:
    """RFC 4252 §7. Signs directly (no accept-probing round trip) since the
    servers we target don't require it."""
    public_key_blob = build_rsa_public_key_blob(private_key.public_key())

    signed_part = (
        encode_string(session.session_id)
        + bytes([messages.SSH_MSG_USERAUTH_REQUEST])
        + encode_string(username.encode("utf-8"))
        + encode_string(b"ssh-connection")
        + encode_string(b"publickey")
        + bytes([1])  # TRUE: a signature is included
        + encode_string(_PUBKEY_ALGORITHM.encode("ascii"))
        + encode_string(public_key_blob)
    )
    signature = private_key.sign(signed_part, padding.PKCS1v15(), hashes.SHA256())
    signature_blob = encode_string(_PUBKEY_ALGORITHM.encode("ascii")) + encode_string(signature)

    request = (
        bytes([messages.SSH_MSG_USERAUTH_REQUEST])
        + encode_string(username.encode("utf-8"))
        + encode_string(b"ssh-connection")
        + encode_string(b"publickey")
        + bytes([1])
        + encode_string(_PUBKEY_ALGORITHM.encode("ascii"))
        + encode_string(public_key_blob)
        + encode_string(signature_blob)
    )
    session.send_message(request)

    payload = _read_until_auth_result(session)
    reader = Reader(payload)
    msg_type = reader.read_byte()
    if msg_type == messages.SSH_MSG_USERAUTH_SUCCESS:
        return
    if msg_type == messages.SSH_MSG_USERAUTH_FAILURE:
        raise AuthenticationError(f"SSH public-key authentication failed for user {username!r}")
    raise ProtocolError(f"Unexpected message during public-key authentication: {msg_type}")
