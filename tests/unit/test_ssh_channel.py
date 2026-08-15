from __future__ import annotations

import pytest

from maxconn.exceptions import ChannelError
from maxconn.transport.ssh import messages
from maxconn.transport.ssh.channel import SSHChannel
from maxconn.transport.ssh.wire import encode_string, encode_uint32


class _FakeSession:
    def __init__(self, payloads: list[bytes]) -> None:
        self._payloads = iter(payloads)
        self.sent: list[bytes] = []

    def recv_message(self) -> bytes:
        return next(self._payloads)

    def send_message(self, payload: bytes) -> None:
        self.sent.append(payload)


def _channel_data_payload(data: bytes) -> bytes:
    return bytes([messages.SSH_MSG_CHANNEL_DATA]) + encode_uint32(0) + encode_string(data)


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
