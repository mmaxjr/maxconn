from __future__ import annotations

from maxconn.transport.ssh import messages
from maxconn.transport.ssh.auth import authenticate_password
from maxconn.transport.ssh.wire import encode_string


class _FakeSession:
    session_id = b"session"

    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.pending_terminal_output: list[bytes] = []
        self._payloads = iter(
            [
                bytes([messages.SSH_MSG_USERAUTH_BANNER])
                + encode_string(b"authorized access only\nline 2")
                + encode_string(b"en"),
                bytes([messages.SSH_MSG_USERAUTH_SUCCESS]),
            ]
        )

    def send_message(self, payload: bytes) -> None:
        self.sent.append(payload)

    def recv_message(self) -> bytes:
        return next(self._payloads)


def test_password_auth_preserves_userauth_banner_for_terminal_display():
    session = _FakeSession()

    authenticate_password(session, "admin", "secret")

    assert session.pending_terminal_output == [
        b"Pre-authentication banner message from server:\r\n"
        b"authorized access only\r\nline 2\r\n"
        b"End of banner message from server\r\n",
        b"Banner language: en\r\n",
    ]
