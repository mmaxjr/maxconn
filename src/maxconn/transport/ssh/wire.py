"""SSH wire-format primitives (RFC 4251 section 5): uint32, string, mpint,
name-list, plus a `Reader` cursor for parsing them back out of a payload."""

from __future__ import annotations

import struct

from maxconn.exceptions import ProtocolError


def encode_uint32(value: int) -> bytes:
    return struct.pack(">I", value)


def encode_string(data: bytes) -> bytes:
    return encode_uint32(len(data)) + data


def encode_name_list(names: list[str]) -> bytes:
    return encode_string(",".join(names).encode("ascii"))


def encode_mpint(value: int) -> bytes:
    if value == 0:
        return encode_uint32(0)

    negative = value < 0
    # Number of bits needed for the magnitude, then round up to a byte
    # boundary and add one bit for the sign so the top bit unambiguously
    # reflects the number's sign per RFC 4251.
    magnitude = -value - 1 if negative else value
    nbytes = (magnitude.bit_length() // 8) + 1
    data = value.to_bytes(nbytes, byteorder="big", signed=True)
    return encode_string(data)


class Reader:
    """Cursor over an SSH message payload, reading fields in RFC 4251 wire format."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def read_byte(self) -> int:
        return self.read_bytes(1)[0]

    def read_bytes(self, n: int) -> bytes:
        if self._pos + n > len(self._data):
            raise ProtocolError(f"Truncated SSH message: needed {n} bytes, {self.remaining()} remain")
        chunk = self._data[self._pos : self._pos + n]
        self._pos += n
        return chunk

    def read_uint32(self) -> int:
        return struct.unpack(">I", self.read_bytes(4))[0]

    def read_string(self) -> bytes:
        length = self.read_uint32()
        return self.read_bytes(length)

    def read_mpint(self) -> int:
        data = self.read_string()
        if not data:
            return 0
        return int.from_bytes(data, byteorder="big", signed=True)

    def read_name_list(self) -> list[str]:
        raw = self.read_string().decode("ascii")
        return raw.split(",") if raw else []

    def remaining(self) -> int:
        return len(self._data) - self._pos

    def remainder(self) -> bytes:
        return self.read_bytes(self.remaining())
