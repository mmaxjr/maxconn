"""Encrypted packet framing for the post-NEWKEYS phase: aes128-ctr encryption
+ HMAC integrity (RFC 4253 sections 6 and 6.4), replacing the
plaintext framing in `packet.py`.

The length field IS encrypted (this is "encrypt-then-nothing", the classic
non-ETM mode), so decoding must decrypt the first cipher block before it can
even learn how many more bytes to read.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import struct
from collections.abc import Callable

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from maxconn.exceptions import ProtocolError
from maxconn.transport.ssh.packet import MAX_PACKET_LENGTH, MIN_PADDING

BLOCK_SIZE = 16  # AES block size
MAC_SIZES = {"hmac-sha2-256": 32, "hmac-sha1": 20}
MAC_HASHES = {"hmac-sha2-256": hashlib.sha256, "hmac-sha1": hashlib.sha1}


class SSHSessionCipher:
    """One direction's worth of state is really two of these - one for
    what we send, one for what we receive - constructed with the matching
    enc/iv/mac keys for that direction."""

    def __init__(
        self,
        enc_key: bytes,
        iv: bytes,
        mac_key: bytes,
        initial_seq: int = 0,
        mac_algorithm: str = "hmac-sha2-256",
    ) -> None:
        cipher = Cipher(algorithms.AES(enc_key), modes.CTR(iv))
        self._encryptor = cipher.encryptor()
        self._decryptor = cipher.decryptor()
        self._mac_key = mac_key
        self._mac_algorithm = mac_algorithm
        self._mac_size = MAC_SIZES[mac_algorithm]
        # RFC 4253 §6.4: the sequence number counts every packet sent on
        # this connection since the start, not just encrypted ones - so
        # this session's first packet is rarely sequence 0 (KEXINIT,
        # KEXDH_INIT/REPLY, and NEWKEYS itself already consumed 0..2).
        self._seq = initial_seq

    def encode_packet(self, payload: bytes, random_bytes: Callable[[int], bytes] | None = None) -> bytes:
        random_bytes = random_bytes or os.urandom
        content_len = 4 + 1 + len(payload)
        padding_length = BLOCK_SIZE - (content_len % BLOCK_SIZE)
        if padding_length < MIN_PADDING:
            padding_length += BLOCK_SIZE

        padding = random_bytes(padding_length)
        packet_length = 1 + len(payload) + padding_length
        plaintext = struct.pack(">I", packet_length) + bytes([padding_length]) + payload + padding

        ciphertext = self._encryptor.update(plaintext)
        mac = self._compute_mac(self._seq, plaintext)
        self._seq = (self._seq + 1) % (2**32)
        return ciphertext + mac

    def decode_packet(self, read_exact: Callable[[int], bytes]) -> bytes:
        first_block_cipher = read_exact(BLOCK_SIZE)
        first_block_plain = self._decryptor.update(first_block_cipher)
        packet_length = struct.unpack(">I", first_block_plain[:4])[0]

        total_frame = 4 + packet_length
        if total_frame < BLOCK_SIZE:
            raise ProtocolError(f"Invalid SSH packet length: {packet_length}")
        if packet_length > MAX_PACKET_LENGTH:
            raise ProtocolError(f"SSH packet length {packet_length} exceeds the {MAX_PACKET_LENGTH}-byte limit")

        remaining_cipher = read_exact(total_frame - BLOCK_SIZE)
        remaining_plain = self._decryptor.update(remaining_cipher)
        plaintext = first_block_plain + remaining_plain

        received_mac = read_exact(self._mac_size)
        expected_mac = self._compute_mac(self._seq, plaintext)
        if not hmac.compare_digest(received_mac, expected_mac):
            raise ProtocolError("SSH packet MAC verification failed")
        self._seq = (self._seq + 1) % (2**32)

        padding_length = plaintext[4]
        payload_length = packet_length - padding_length - 1
        if payload_length < 0:
            raise ProtocolError(f"Invalid SSH packet: padding_length {padding_length} exceeds packet body")
        return plaintext[5 : 5 + payload_length]

    def _compute_mac(self, seq: int, plaintext: bytes) -> bytes:
        return hmac.new(self._mac_key, struct.pack(">I", seq) + plaintext, MAC_HASHES[self._mac_algorithm]).digest()
