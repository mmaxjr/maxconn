import pytest

from maxconn.exceptions import ProtocolError
from maxconn.transport.ssh.handshake import CLIENT_ID, recv_version, send_version


class _FakeSocket:
    def __init__(self) -> None:
        self.sent = b""

    def sendall(self, data: bytes) -> None:
        self.sent += data


class _FakeReader:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = list(lines)

    def read_line(self) -> bytes:
        if not self._lines:
            raise AssertionError("no more lines")
        return self._lines.pop(0)


def test_send_version_writes_crlf_terminated_banner():
    sock = _FakeSocket()
    returned = send_version(sock)
    assert sock.sent == (CLIENT_ID + "\r\n").encode("ascii")
    assert returned == CLIENT_ID.encode("ascii")


def test_recv_version_returns_first_ssh_line():
    reader = _FakeReader([b"SSH-2.0-OpenSSH_9.6"])
    assert recv_version(reader) == b"SSH-2.0-OpenSSH_9.6"


def test_recv_version_skips_preamble_lines():
    reader = _FakeReader([b"Welcome to ACME router", b"SSH-2.0-libssh_0.10"])
    assert recv_version(reader) == b"SSH-2.0-libssh_0.10"


def test_recv_version_raises_if_no_banner_found():
    reader = _FakeReader([b"not a banner"] * 60)
    with pytest.raises(ProtocolError):
        recv_version(reader)
