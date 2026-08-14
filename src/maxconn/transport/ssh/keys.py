"""SSH session key derivation (RFC 4253 section 7.2)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from maxconn.transport.ssh.wire import encode_mpint


def _derive(
    shared_secret: int, exchange_hash: bytes, session_id: bytes, tag: bytes, length: int, hash_name: str
) -> bytes:
    # RFC 4253 §7.2: K1 = HASH(K || H || X || session_id), extended with
    # HASH(K || H || K1 || K2 || ...) if more bytes are needed than one
    # hash output provides. K is mpint-encoded; H and session_id are used
    # verbatim (no length prefix). HASH must be the same hash algorithm
    # used to compute the exchange hash H itself (sha1 when
    # diffie-hellman-group14-sha1 was negotiated, sha256 otherwise) - using
    # a different one here silently produces keys a compliant peer never
    # derives, so every packet after NEWKEYS fails MAC verification.
    k_mpint = encode_mpint(shared_secret)
    output = hashlib.new(hash_name, k_mpint + exchange_hash + tag + session_id).digest()
    while len(output) < length:
        output += hashlib.new(hash_name, k_mpint + exchange_hash + output).digest()
    return output[:length]


@dataclass
class SessionKeys:
    iv_client_to_server: bytes
    iv_server_to_client: bytes
    enc_key_client_to_server: bytes
    enc_key_server_to_client: bytes
    mac_key_client_to_server: bytes
    mac_key_server_to_client: bytes


def derive_session_keys(
    shared_secret: int,
    exchange_hash: bytes,
    session_id: bytes,
    *,
    hash_name: str = "sha256",
    iv_length: int = 16,
    enc_key_length: int = 16,
    mac_key_length_client_to_server: int = 32,
    mac_key_length_server_to_client: int = 32,
) -> SessionKeys:
    return SessionKeys(
        iv_client_to_server=_derive(shared_secret, exchange_hash, session_id, b"A", iv_length, hash_name),
        iv_server_to_client=_derive(shared_secret, exchange_hash, session_id, b"B", iv_length, hash_name),
        enc_key_client_to_server=_derive(shared_secret, exchange_hash, session_id, b"C", enc_key_length, hash_name),
        enc_key_server_to_client=_derive(shared_secret, exchange_hash, session_id, b"D", enc_key_length, hash_name),
        mac_key_client_to_server=_derive(
            shared_secret, exchange_hash, session_id, b"E", mac_key_length_client_to_server, hash_name
        ),
        mac_key_server_to_client=_derive(
            shared_secret, exchange_hash, session_id, b"F", mac_key_length_server_to_client, hash_name
        ),
    )
