"""SSH_MSG_KEXINIT construction and parsing (RFC 4253 section 7.1).

The actual key exchange (Diffie-Hellman group14-sha256) lives in
`diffie_hellman.py`; this module only handles the algorithm-negotiation
message both sides exchange before it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from maxconn.exceptions import ProtocolError
from maxconn.transport.ssh import messages
from maxconn.transport.ssh.wire import Reader, encode_name_list, encode_uint32

KEX_ALGORITHMS = ["ecdh-sha2-nistp256", "diffie-hellman-group14-sha256", "diffie-hellman-group14-sha1"]
# "rsa-sha2-256" (RFC 8332) is the modern SHA-256-based signature scheme for
# RSA host keys; plain "ssh-rsa" (SHA-1) is offered only as a fallback for
# older servers, since most current implementations reject SHA-1 signatures.
SERVER_HOST_KEY_ALGORITHMS = ["ecdsa-sha2-nistp256", "rsa-sha2-256", "rsa-sha2-512", "ssh-rsa"]
ENCRYPTION_ALGORITHMS = ["aes128-ctr"]
MAC_ALGORITHMS = ["hmac-sha2-256", "hmac-sha1"]
COMPRESSION_ALGORITHMS = ["none"]


def build_kexinit(
    cookie: bytes | None = None,
    *,
    kex_algorithms: list[str] | None = None,
    server_host_key_algorithms: list[str] | None = None,
    encryption_algorithms: list[str] | None = None,
    mac_algorithms: list[str] | None = None,
    compression_algorithms: list[str] | None = None,
) -> bytes:
    if cookie is None:
        cookie = os.urandom(16)
    elif len(cookie) != 16:
        raise ValueError("KEXINIT cookie must be exactly 16 bytes")

    parts = [
        bytes([messages.SSH_MSG_KEXINIT]),
        cookie,
        encode_name_list(kex_algorithms or KEX_ALGORITHMS),
        encode_name_list(server_host_key_algorithms or SERVER_HOST_KEY_ALGORITHMS),
        encode_name_list(encryption_algorithms or ENCRYPTION_ALGORITHMS),
        encode_name_list(encryption_algorithms or ENCRYPTION_ALGORITHMS),
        encode_name_list(mac_algorithms or MAC_ALGORITHMS),
        encode_name_list(mac_algorithms or MAC_ALGORITHMS),
        encode_name_list(compression_algorithms or COMPRESSION_ALGORITHMS),
        encode_name_list(compression_algorithms or COMPRESSION_ALGORITHMS),
        encode_name_list([]),
        encode_name_list([]),
        bytes([0]),  # first_kex_packet_follows: we never guess-send a kex packet early
        encode_uint32(0),  # reserved
    ]
    return b"".join(parts)


@dataclass
class KexInit:
    cookie: bytes
    kex_algorithms: list[str]
    server_host_key_algorithms: list[str]
    encryption_algorithms_client_to_server: list[str]
    encryption_algorithms_server_to_client: list[str]
    mac_algorithms_client_to_server: list[str]
    mac_algorithms_server_to_client: list[str]
    compression_algorithms_client_to_server: list[str]
    compression_algorithms_server_to_client: list[str]
    languages_client_to_server: list[str] = field(default_factory=list)
    languages_server_to_client: list[str] = field(default_factory=list)
    first_kex_packet_follows: bool = False


def parse_kexinit(payload: bytes) -> KexInit:
    reader = Reader(payload)
    msg_type = reader.read_byte()
    if msg_type != messages.SSH_MSG_KEXINIT:
        raise ProtocolError(f"Expected SSH_MSG_KEXINIT ({messages.SSH_MSG_KEXINIT}), got {msg_type}")

    cookie = reader.read_bytes(16)
    kex_algorithms = reader.read_name_list()
    server_host_key_algorithms = reader.read_name_list()
    enc_c2s = reader.read_name_list()
    enc_s2c = reader.read_name_list()
    mac_c2s = reader.read_name_list()
    mac_s2c = reader.read_name_list()
    comp_c2s = reader.read_name_list()
    comp_s2c = reader.read_name_list()
    lang_c2s = reader.read_name_list()
    lang_s2c = reader.read_name_list()
    first_kex_packet_follows = bool(reader.read_byte())
    # trailing reserved uint32 intentionally ignored

    return KexInit(
        cookie=cookie,
        kex_algorithms=kex_algorithms,
        server_host_key_algorithms=server_host_key_algorithms,
        encryption_algorithms_client_to_server=enc_c2s,
        encryption_algorithms_server_to_client=enc_s2c,
        mac_algorithms_client_to_server=mac_c2s,
        mac_algorithms_server_to_client=mac_s2c,
        compression_algorithms_client_to_server=comp_c2s,
        compression_algorithms_server_to_client=comp_s2c,
        languages_client_to_server=lang_c2s,
        languages_server_to_client=lang_s2c,
        first_kex_packet_follows=first_kex_packet_follows,
    )


def negotiate(client: list[str], server: list[str], what: str) -> str:
    """Pick the first client-preferred algorithm the server also offers (RFC 4253 §7.1)."""
    for algorithm in client:
        if algorithm in server:
            return algorithm
    raise ProtocolError(f"No matching {what} algorithm: client offers {client}, server offers {server}")
