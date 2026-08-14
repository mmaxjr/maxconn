import pytest

from maxconn.exceptions import ProtocolError
from maxconn.transport.ssh.packet import MAX_PACKET_LENGTH
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


def test_initial_seq_must_match_on_both_sides():
    enc_key, iv, mac_key = b"\xee" * 16, b"\xff" * 16, b"\x12" * 32
    writer = SSHSessionCipher(enc_key, iv, mac_key, initial_seq=3)
    reader = SSHSessionCipher(enc_key, iv, mac_key, initial_seq=3)

    packet = writer.encode_packet(b"post-newkeys message")
    assert reader.decode_packet(_make_reader(packet)) == b"post-newkeys message"


def test_mismatched_initial_seq_fails_mac_verification():
    enc_key, iv, mac_key = b"\xee" * 16, b"\xff" * 16, b"\x12" * 32
    writer = SSHSessionCipher(enc_key, iv, mac_key, initial_seq=3)
    reader = SSHSessionCipher(enc_key, iv, mac_key, initial_seq=0)  # forgot to offset

    packet = writer.encode_packet(b"post-newkeys message")
    with pytest.raises(ProtocolError):
        reader.decode_packet(_make_reader(packet))


def test_wrong_mac_key_fails_verification():
    enc_key, iv = b"\xaa" * 16, b"\xbb" * 16
    writer = SSHSessionCipher(enc_key, iv, mac_key=b"\xcc" * 32)
    reader = SSHSessionCipher(enc_key, iv, mac_key=b"\xdd" * 32)  # different mac key

    packet = writer.encode_packet(b"payload")
    with pytest.raises(ProtocolError):
        reader.decode_packet(_make_reader(packet))


def test_decode_rejects_implausibly_large_packet_length_without_reading_the_body():
    # A malicious/misbehaving peer sends an oversized encrypted length
    # field then stalls: this must be rejected right after decrypting the
    # first block, before requesting (and buffering) the rest of a
    # multi-hundred-kilobyte body.
    enc_key, iv, mac_key = b"\x21" * 16, b"\x22" * 16, b"\x23" * 32
    writer = SSHSessionCipher(enc_key, iv, mac_key)
    reader = SSHSessionCipher(enc_key, iv, mac_key)

    oversized_payload = b"x" * (MAX_PACKET_LENGTH + 1000)
    packet = writer.encode_packet(oversized_payload)

    state = {"data": packet}
    calls = []

    def read_exact(n: int) -> bytes:
        chunk = state["data"][:n]
        state["data"] = state["data"][n:]
        calls.append(n)
        return chunk

    with pytest.raises(ProtocolError):
        reader.decode_packet(read_exact)
    # Only the first 16-byte cipher block should have been read - never the
    # rest of the (attacker-controlled) oversized body.
    assert calls == [16]


def test_hmac_sha1_packets_round_trip_for_legacy_servers():
    enc_key, iv, mac_key = b"\x13" * 16, b"\x14" * 16, b"\x15" * 20
    writer = SSHSessionCipher(enc_key, iv, mac_key, mac_algorithm="hmac-sha1")
    reader = SSHSessionCipher(enc_key, iv, mac_key, mac_algorithm="hmac-sha1")

    packet = writer.encode_packet(b"legacy mac")

    assert reader.decode_packet(_make_reader(packet)) == b"legacy mac"
