"""SSH Binary Packet Protocol framing (RFC 4253 section 6).

This module handles only the unencrypted packet shape:

    uint32    packet_length
    byte      padding_length
    byte[n1]  payload
    byte[n2]  random padding

It's used for the plaintext handshake phase (version exchange onward,
before NEWKEYS). Once a cipher is negotiated, the encrypted/MAC'd framing
in `session.py` takes over.
"""

from __future__ import annotations

import os
import struct
from collections.abc import Callable

from maxconn.exceptions import ProtocolError

MIN_PADDING = 4


def encode_binary_packet(
    payload: bytes,
    block_size: int = 8,
    random_bytes: Callable[[int], bytes] = os.urandom,
) -> bytes:
    # RFC 4253 §6: the concatenation of packet_length, padding_length,
    # payload, and padding - INCLUDING the 4-byte packet_length field
    # itself - must be a multiple of the block size. The *value* written
    # into the packet_length field, however, does NOT count itself.
    total_before_padding = 4 + 1 + len(payload)  # length field + padding_length byte + payload
    padding_length = block_size - (total_before_padding % block_size)
    if padding_length < MIN_PADDING:
        padding_length += block_size

    padding = random_bytes(padding_length)
    packet_length = 1 + len(payload) + padding_length
    return struct.pack(">I", packet_length) + bytes([padding_length]) + payload + padding


def decode_binary_packet(read_exact: Callable[[int], bytes]) -> bytes:
    length_bytes = read_exact(4)
    if len(length_bytes) != 4:
        raise ProtocolError("Connection closed while reading SSH packet length")
    packet_length = struct.unpack(">I", length_bytes)[0]

    body = read_exact(packet_length)
    if len(body) != packet_length:
        raise ProtocolError("Connection closed while reading SSH packet body")

    padding_length = body[0]
    payload_length = packet_length - padding_length - 1
    if payload_length < 0:
        raise ProtocolError(f"Invalid SSH packet: padding_length {padding_length} exceeds packet body")

    return body[1 : 1 + payload_length]
