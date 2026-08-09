import pytest

from maxconn.exceptions import ProtocolError
from maxconn.transport.ssh.session import SSHSessionCipher


def _make_reader(data: bytes):
    state = {"data": data}

    def read_exact(n: int) -> bytes:
        chunk = state["data"][:n]
        state["data"] = state["data"][n:]
        return chunk

    return read_exact


def test_encode_decode_round_trip_single_packet():
    enc_key, iv, mac_key = b"\x01" * 16, b"\x02" * 16, b"\x03" * 32
    writer = SSHSessionCipher(enc_key, iv, mac_key)
    reader = SSHSessionCipher(enc_key, iv, mac_key)

    packet = writer.encode_packet(b"hello world")
    assert reader.decode_packet(_make_reader(packet)) == b"hello world"


def test_encode_decode_round_trip_multiple_packets_advance_sequence():
    enc_key, iv, mac_key = b"\x11" * 16, b"\x22" * 16, b"\x33" * 32
    writer = SSHSessionCipher(enc_key, iv, mac_key)
    reader = SSHSessionCipher(enc_key, iv, mac_key)

    for i in range(5):
        payload = f"message {i}".encode()
        packet = writer.encode_packet(payload)
        assert reader.decode_packet(_make_reader(packet)) == payload


def test_encode_decode_round_trip_empty_payload():
    enc_key, iv, mac_key = b"\x44" * 16, b"\x55" * 16, b"\x66" * 32
    writer = SSHSessionCipher(enc_key, iv, mac_key)
    reader = SSHSessionCipher(enc_key, iv, mac_key)

    packet = writer.encode_packet(b"")
    assert reader.decode_packet(_make_reader(packet)) == b""


def test_tampered_ciphertext_fails_mac_verification():
    enc_key, iv, mac_key = b"\x77" * 16, b"\x88" * 16, b"\x99" * 32
    writer = SSHSessionCipher(enc_key, iv, mac_key)
    reader = SSHSessionCipher(enc_key, iv, mac_key)

    packet = bytearray(writer.encode_packet(b"do not trust me"))
    packet[0] ^= 0xFF  # flip a bit in the (encrypted) length field

    with pytest.raises(ProtocolError):
        reader.decode_packet(_make_reader(bytes(packet)))


def test_wrong_mac_key_fails_verification():
    enc_key, iv = b"\xaa" * 16, b"\xbb" * 16
    writer = SSHSessionCipher(enc_key, iv, mac_key=b"\xcc" * 32)
    reader = SSHSessionCipher(enc_key, iv, mac_key=b"\xdd" * 32)  # different mac key

    packet = writer.encode_packet(b"payload")
    with pytest.raises(ProtocolError):
        reader.decode_packet(_make_reader(packet))
