"""Diffie-Hellman group14-sha256 key exchange (RFC 4253 section 8, group
from RFC 3526 section 3 - the 2048-bit MODP "group 14")."""

from __future__ import annotations

import hashlib
import secrets
import socket
from dataclasses import dataclass

from maxconn.exceptions import ProtocolError
from maxconn.transport.ssh import messages
from maxconn.transport.ssh.packet import decode_binary_packet, encode_binary_packet
from maxconn.transport.ssh.socket_reader import SocketReader
from maxconn.transport.ssh.wire import Reader, encode_mpint, encode_string

# RFC 3526 section 3, 2048-bit MODP Group ("group 14").
_P_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD"
    "129024E088A67CC74020BBEA63B139B22514A08798E3404"
    "DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C"
    "245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406"
    "B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE"
    "45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD"
    "24CF5F83655D23DCA3AD961C62F356208552BB9ED529077"
    "096966D670C354E4ABC9804F1746C08CA18217C32905E46"
    "2E36CE3BE39E772C180E86039B2783A2EC07A28FB5C55DF"
    "06F4C52C9DE2BCBF6955817183995497CEA956AE515D226"
    "1898FA051015728E5A8AACAA68FFFFFFFFFFFFFFFF"
)
P = int(_P_HEX, 16)
G = 2


@dataclass
class KexResult:
    shared_secret: int  # K
    exchange_hash: bytes  # H
    host_key_blob: bytes  # K_S, as received from the server
    signature_blob: bytes  # raw "string" signature blob from KEXDH_REPLY


def perform_diffie_hellman(
    sock: socket.socket,
    reader: SocketReader,
    client_version: bytes,
    server_version: bytes,
    client_kexinit_payload: bytes,
    server_kexinit_payload: bytes,
) -> KexResult:
    x = secrets.randbelow(P - 3) + 2  # private exponent, 2 <= x <= P-2
    e = pow(G, x, P)

    packet = encode_binary_packet(bytes([messages.SSH_MSG_KEXDH_INIT]) + encode_mpint(e))
    sock.sendall(packet)

    reply_payload = decode_binary_packet(reader.read_exact)
    reply = Reader(reply_payload)
    msg_type = reply.read_byte()
    if msg_type != messages.SSH_MSG_KEXDH_REPLY:
        raise ProtocolError(f"Expected SSH_MSG_KEXDH_REPLY ({messages.SSH_MSG_KEXDH_REPLY}), got {msg_type}")

    host_key_blob = reply.read_string()
    f = reply.read_mpint()
    signature_blob = reply.read_string()

    shared_secret = pow(f, x, P)
    exchange_hash = compute_exchange_hash(
        client_version=client_version,
        server_version=server_version,
        client_kexinit_payload=client_kexinit_payload,
        server_kexinit_payload=server_kexinit_payload,
        host_key_blob=host_key_blob,
        e=e,
        f=f,
        shared_secret=shared_secret,
    )
    return KexResult(shared_secret, exchange_hash, host_key_blob, signature_blob)


def compute_exchange_hash(
    *,
    client_version: bytes,
    server_version: bytes,
    client_kexinit_payload: bytes,
    server_kexinit_payload: bytes,
    host_key_blob: bytes,
    e: int,
    f: int,
    shared_secret: int,
) -> bytes:
    """H = SHA256(V_C || V_S || I_C || I_S || K_S || e || f || K), RFC 4253 §8."""
    hash_input = b"".join(
        [
            encode_string(client_version),
            encode_string(server_version),
            encode_string(client_kexinit_payload),
            encode_string(server_kexinit_payload),
            encode_string(host_key_blob),
            encode_mpint(e),
            encode_mpint(f),
            encode_mpint(shared_secret),
        ]
    )
    return hashlib.sha256(hash_input).digest()
