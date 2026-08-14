"""Unit tests for the parts of the DH exchange that need a misbehaving peer
to exercise - a real test SSH server never sends a degenerate public value,
so these use a fake socket/reader instead of the paramiko-backed fixture.
"""

from __future__ import annotations

import pytest

from maxconn.exceptions import ProtocolError
from maxconn.transport.ssh import messages
from maxconn.transport.ssh.diffie_hellman import G, P, perform_diffie_hellman
from maxconn.transport.ssh.packet import encode_binary_packet
from maxconn.transport.ssh.wire import encode_mpint, encode_string


class _FakeSocket:
    def sendall(self, data: bytes) -> None:
        pass


class _FakeReader:
    def __init__(self, packet: bytes) -> None:
        self._buffer = packet

    def read_exact(self, n: int) -> bytes:
        chunk, self._buffer = self._buffer[:n], self._buffer[n:]
        return chunk


def _build_kexdh_reply(f: int) -> bytes:
    payload = (
        bytes([messages.SSH_MSG_KEXDH_REPLY])
        + encode_string(b"fake-host-key-blob")
        + encode_mpint(f)
        + encode_string(b"fake-signature-blob")
    )
    return encode_binary_packet(payload)


@pytest.mark.parametrize("degenerate_f", [0, 1, P - 1, P])
def test_perform_diffie_hellman_rejects_out_of_range_public_value(degenerate_f):
    reader = _FakeReader(_build_kexdh_reply(degenerate_f))
    with pytest.raises(ProtocolError):
        perform_diffie_hellman(
            _FakeSocket(),
            reader,
            client_version=b"SSH-2.0-client",
            server_version=b"SSH-2.0-server",
            client_kexinit_payload=b"client-kexinit",
            server_kexinit_payload=b"server-kexinit",
        )


def test_perform_diffie_hellman_accepts_a_plausible_in_range_public_value():
    # G itself (2) is a valid, in-range public value - this just proves the
    # range check doesn't reject legitimate values too.
    reader = _FakeReader(_build_kexdh_reply(G))
    result = perform_diffie_hellman(
        _FakeSocket(),
        reader,
        client_version=b"SSH-2.0-client",
        server_version=b"SSH-2.0-server",
        client_kexinit_payload=b"client-kexinit",
        server_kexinit_payload=b"server-kexinit",
    )
    assert isinstance(result.shared_secret, int)
