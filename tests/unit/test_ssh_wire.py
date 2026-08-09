import pytest

from maxconn.transport.ssh.wire import (
    Reader,
    encode_mpint,
    encode_string,
    encode_uint32,
)


def test_encode_uint32():
    assert encode_uint32(0) == bytes.fromhex("00000000")
    assert encode_uint32(1) == bytes.fromhex("00000001")
    assert encode_uint32(0x12345678) == bytes.fromhex("12345678")


def test_encode_string():
    assert encode_string(b"") == bytes.fromhex("00000000")
    assert encode_string(b"ssh-rsa") == encode_uint32(7) + b"ssh-rsa"


# Fixed vectors from RFC 4251 section 5 ("mpint" examples).
def test_encode_mpint_zero():
    assert encode_mpint(0) == bytes.fromhex("00000000")


def test_encode_mpint_positive_needing_no_sign_padding():
    # 0x9a378f9b2e332a7 has an odd hex-digit count; the natural byte
    # boundary already puts a clear high bit (0x09) in the first byte,
    # so no extra 0x00 sign byte is needed - 8 bytes of data.
    assert encode_mpint(0x9A378F9B2E332A7) == bytes.fromhex("0000000809a378f9b2e332a7")


def test_encode_mpint_positive_high_bit_needs_sign_byte():
    # 0x80 alone would have its high bit set (read as negative), so a
    # leading 0x00 byte is required to keep it unambiguously positive.
    assert encode_mpint(0x80) == bytes.fromhex("0000000200" "80")


@pytest.mark.parametrize(
    "value",
    [0, 1, -1, 127, 128, -128, -129, 255, 256, -1234, 0x9A378F9B2E332A7, -0xDEADBEEF, 2**64, -(2**64)],
)
def test_encode_mpint_round_trips_through_reader(value):
    encoded = encode_mpint(value)
    reader = Reader(encoded)
    assert reader.read_mpint() == value


@pytest.mark.parametrize("value", [0, 1, -1, 127, 128, -128, -129])
def test_encode_mpint_has_no_redundant_leading_byte(value):
    # RFC 4251: "unnecessary leading bytes with the value 0 or 255 MUST
    # NOT be included" - i.e. the encoding must be minimal.
    encoded = encode_mpint(value)
    length = int.from_bytes(encoded[:4], "big")
    data = encoded[4:]
    assert len(data) == length
    if length >= 2:
        first, second = data[0], data[1]
        redundant_positive = first == 0x00 and second < 0x80
        redundant_negative = first == 0xFF and second >= 0x80
        assert not redundant_positive
        assert not redundant_negative


def test_reader_round_trip_mixed_fields():
    payload = encode_uint32(42) + encode_string(b"hello") + encode_mpint(0x9A378F9B2E332A7)
    reader = Reader(payload)
    assert reader.read_uint32() == 42
    assert reader.read_string() == b"hello"
    assert reader.read_mpint() == 0x9A378F9B2E332A7


def test_reader_read_byte_and_bytes():
    reader = Reader(b"\x01\x02\x03\x04")
    assert reader.read_byte() == 1
    assert reader.read_bytes(2) == b"\x02\x03"
    assert reader.read_byte() == 4


def test_reader_read_name_list():
    payload = encode_string(b"aes128-ctr,aes256-ctr")
    reader = Reader(payload)
    assert reader.read_name_list() == ["aes128-ctr", "aes256-ctr"]


def test_reader_read_name_list_empty():
    payload = encode_string(b"")
    reader = Reader(payload)
    assert reader.read_name_list() == []
