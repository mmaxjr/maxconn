from __future__ import annotations

import pytest

from maxconn.exceptions import ChannelError
from maxconn.transport.ssh import messages
from maxconn.transport.ssh.channel import SSHChannel, open_session_channel
from maxconn.transport.ssh.wire import encode_string, encode_uint32


class _FakeSession:
    def __init__(self, payloads: list[bytes]) -> None:
        self._payloads = iter(payloads)
        self.sent: list[bytes] = []
        self.pending_terminal_output: list[bytes] = []

    def recv_message(self) -> bytes:
        return next(self._payloads)

    def send_message(self, payload: bytes) -> None:
        self.sent.append(payload)


def _channel_data_payload(data: bytes) -> bytes:
    return bytes([messages.SSH_MSG_CHANNEL_DATA]) + encode_uint32(0) + encode_string(data)


def _channel_open_confirmation_payload() -> bytes:
    return (
        bytes([messages.SSH_MSG_CHANNEL_OPEN_CONFIRMATION])
        + encode_uint32(0)
        + encode_uint32(1)
        + encode_uint32(2 * 1024 * 1024)
        + encode_uint32(32768)
    )


@pytest.mark.parametrize(
    "keepalive_type",
    [messages.SSH_MSG_IGNORE, messages.SSH_MSG_DEBUG, messages.SSH_MSG_GLOBAL_REQUEST],
)
def test_recv_data_skips_legitimate_keepalive_messages_instead_of_erroring(keepalive_type):
    # Regression: SSH_MSG_IGNORE/DEBUG/GLOBAL_REQUEST are legitimate
    # messages a server or SSH-aware middlebox can send mid-session (e.g. a
    # keepalive), but recv_data() treated any of them as a hard protocol
    # error and tore down an otherwise-healthy channel.
    session = _FakeSession([bytes([keepalive_type]), _channel_data_payload(b"hello")])
    channel = SSHChannel(session, local_id=0, peer_id=1)

    assert channel.recv_data() == b"hello"


def test_recv_data_still_raises_on_a_genuinely_unexpected_message_type():
    session = _FakeSession([bytes([255])])  # not a real SSH message type
    channel = SSHChannel(session, local_id=0, peer_id=1)

    with pytest.raises(ChannelError):
        channel.recv_data()


def test_open_session_channel_skips_global_request_before_open_confirmation():
    session = _FakeSession([bytes([messages.SSH_MSG_GLOBAL_REQUEST]), _channel_open_confirmation_payload()])

    channel = open_session_channel(session)

    assert channel.peer_id == 1


def test_open_session_channel_exposes_pending_auth_banner_on_first_recv():
    session = _FakeSession([_channel_open_confirmation_payload(), _channel_data_payload(b"device>")])
    session.pending_terminal_output.append(b"Pre-authentication banner message from server:\r\nhello\r\n")

    channel = open_session_channel(session)

    assert channel.recv_data() == b"Pre-authentication banner message from server:\r\nhello\r\n"
    assert channel.recv_data() == b"device>"
    assert session.pending_terminal_output == []


def test_close_ignores_socket_already_aborted_by_remote():
    session = _FakeSession([])

    def raise_aborted(_payload: bytes) -> None:
        raise ConnectionAbortedError("closed")

    session.send_message = raise_aborted
    channel = SSHChannel(session, local_id=0, peer_id=1)

    channel.close()

    assert channel.closed
