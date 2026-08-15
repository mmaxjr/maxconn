"""SSH channel handling: open a session channel and run exec/shell commands
(RFC 4254 sections 4-6). v0.1 does not track outgoing flow control (channel
window replenishment for data *we* send) - fine for interactive command/CLI
use, not for bulk transfers."""

from __future__ import annotations

from maxconn.exceptions import ChannelError
from maxconn.transport.ssh import messages
from maxconn.transport.ssh.negotiate import EncryptedSession
from maxconn.transport.ssh.wire import Reader, encode_string, encode_uint32

INITIAL_WINDOW_SIZE = 2 * 1024 * 1024
MAX_PACKET_SIZE = 32768

_CONTROL_ONLY_MESSAGES = (
    messages.SSH_MSG_CHANNEL_WINDOW_ADJUST,
    messages.SSH_MSG_CHANNEL_SUCCESS,
    messages.SSH_MSG_CHANNEL_FAILURE,
    messages.SSH_MSG_CHANNEL_REQUEST,  # e.g. "exit-status" - informational only
    messages.SSH_MSG_CHANNEL_EOF,
    # Connection-level messages a server or SSH-aware middlebox can
    # legitimately send at any point in the session (e.g. a keepalive
    # SSH_MSG_IGNORE) - not tied to any particular channel, safe to skip.
    messages.SSH_MSG_IGNORE,
    messages.SSH_MSG_DEBUG,
    messages.SSH_MSG_GLOBAL_REQUEST,
)


class SSHChannel:
    def __init__(self, session: EncryptedSession, local_id: int, peer_id: int) -> None:
        self._session = session
        self.local_id = local_id
        self.peer_id = peer_id
        self._closed = False

    def request_exec(self, command: str) -> None:
        payload = (
            bytes([messages.SSH_MSG_CHANNEL_REQUEST])
            + encode_uint32(self.peer_id)
            + encode_string(b"exec")
            + bytes([0])  # want_reply = False: caller reads the command output instead
            + encode_string(command.encode("utf-8"))
        )
        self._session.send_message(payload)

    def request_shell(self) -> None:
        pty_payload = (
            bytes([messages.SSH_MSG_CHANNEL_REQUEST])
            + encode_uint32(self.peer_id)
            + encode_string(b"pty-req")
            + bytes([0])
            + encode_string(b"xterm")
            + encode_uint32(80)
            + encode_uint32(24)
            + encode_uint32(640)
            + encode_uint32(480)
            + encode_string(b"")
        )
        self._session.send_message(pty_payload)

        shell_payload = (
            bytes([messages.SSH_MSG_CHANNEL_REQUEST])
            + encode_uint32(self.peer_id)
            + encode_string(b"shell")
            + bytes([0])
        )
        self._session.send_message(shell_payload)

    def request_subsystem(self, name: str) -> None:
        payload = (
            bytes([messages.SSH_MSG_CHANNEL_REQUEST])
            + encode_uint32(self.peer_id)
            + encode_string(b"subsystem")
            + bytes([0])
            + encode_string(name.encode("utf-8"))
        )
        self._session.send_message(payload)

    def send_data(self, data: bytes) -> None:
        payload = bytes([messages.SSH_MSG_CHANNEL_DATA]) + encode_uint32(self.peer_id) + encode_string(data)
        self._session.send_message(payload)

    def recv_data(self) -> bytes:
        """Read one channel message and return its data payload (empty
        bytes for control-only messages like a window adjustment)."""
        while True:
            payload = self._session.recv_message()
            reader = Reader(payload)
            msg_type = reader.read_byte()

            if msg_type == messages.SSH_MSG_CHANNEL_DATA:
                reader.read_uint32()  # recipient channel (ours; unused)
                return reader.read_string()
            if msg_type == messages.SSH_MSG_CHANNEL_EXTENDED_DATA:
                reader.read_uint32()
                reader.read_uint32()  # data_type_code (e.g. stderr)
                return reader.read_string()
            if msg_type in _CONTROL_ONLY_MESSAGES:
                continue
            if msg_type == messages.SSH_MSG_CHANNEL_CLOSE:
                self._closed = True
                close_payload = bytes([messages.SSH_MSG_CHANNEL_CLOSE]) + encode_uint32(self.peer_id)
                self._session.send_message(close_payload)
                return b""

            raise ChannelError(f"Unexpected message on SSH channel: type {msg_type}")

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if not self._closed:
            self._session.send_message(bytes([messages.SSH_MSG_CHANNEL_CLOSE]) + encode_uint32(self.peer_id))
            self._closed = True


def open_session_channel(session: EncryptedSession, local_id: int = 0) -> SSHChannel:
    request = (
        bytes([messages.SSH_MSG_CHANNEL_OPEN])
        + encode_string(b"session")
        + encode_uint32(local_id)
        + encode_uint32(INITIAL_WINDOW_SIZE)
        + encode_uint32(MAX_PACKET_SIZE)
    )
    session.send_message(request)

    payload = session.recv_message()
    reader = Reader(payload)
    msg_type = reader.read_byte()

    if msg_type == messages.SSH_MSG_CHANNEL_OPEN_FAILURE:
        reader.read_uint32()  # recipient channel
        reason_code = reader.read_uint32()
        description = reader.read_string().decode(errors="replace")
        raise ChannelError(f"SSH channel open failed (reason {reason_code}): {description}")
    if msg_type != messages.SSH_MSG_CHANNEL_OPEN_CONFIRMATION:
        raise ChannelError(f"Unexpected reply to SSH_MSG_CHANNEL_OPEN: type {msg_type}")

    reader.read_uint32()  # recipient channel (== local_id, echoed back)
    peer_id = reader.read_uint32()
    reader.read_uint32()  # peer's initial window size (unused, see module docstring)
    reader.read_uint32()  # peer's max packet size (unused, same reason)

    return SSHChannel(session, local_id, peer_id)
