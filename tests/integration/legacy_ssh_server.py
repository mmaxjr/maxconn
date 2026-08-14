"""A minimal fake SSH server that only speaks the legacy
diffie-hellman-group14-sha1 / ssh-rsa / hmac-sha1 combination.

This exists because the paramiko test dependency used elsewhere in this
suite has *dropped* group14-sha1 entirely in current versions (it isn't in
`Transport._kex_info` any more), so it can no longer stand in for the one
real-world server (OpenSSH_6.2) that maxconn's compatibility fallback
targets. Server-side crypto here is built from maxconn's own from-scratch
primitives (the same functions the client uses, run in the opposite
direction) rather than reimplemented independently - it is not as strong a
proof as the paramiko-backed tests elsewhere, but it does exercise the real
client code in `negotiate.py` end-to-end against protocol-correct peer
behavior for the one path paramiko can no longer help test.
"""

from __future__ import annotations

import socket
import threading
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from maxconn.transport.ssh import messages
from maxconn.transport.ssh.diffie_hellman import G, P, compute_exchange_hash
from maxconn.transport.ssh.handshake import recv_version
from maxconn.transport.ssh.kex import build_kexinit, parse_kexinit
from maxconn.transport.ssh.keys import derive_session_keys
from maxconn.transport.ssh.packet import decode_binary_packet, encode_binary_packet
from maxconn.transport.ssh.session import SSHSessionCipher
from maxconn.transport.ssh.socket_reader import SocketReader
from maxconn.transport.ssh.wire import Reader, encode_mpint, encode_string


def _rsa_host_key_blob(public_key: rsa.RSAPublicKey) -> bytes:
    numbers = public_key.public_numbers()
    return encode_string(b"ssh-rsa") + encode_mpint(numbers.e) + encode_mpint(numbers.n)


def _serve_one_connection(conn: socket.socket, host_key: rsa.RSAPrivateKey) -> None:
    reader = SocketReader(conn)
    try:
        conn.sendall(b"SSH-2.0-fakelegacy\r\n")
        client_version = recv_version(reader)
        server_version = b"SSH-2.0-fakelegacy"

        client_kexinit_payload = decode_binary_packet(reader.read_exact)
        parse_kexinit(client_kexinit_payload)  # validate it parses; content unused here

        server_kexinit_payload = build_kexinit(
            kex_algorithms=["diffie-hellman-group14-sha1"],
            server_host_key_algorithms=["ssh-rsa"],
            encryption_algorithms=["aes128-ctr"],
            mac_algorithms=["hmac-sha1"],
        )
        conn.sendall(encode_binary_packet(server_kexinit_payload))

        kexdh_init_payload = decode_binary_packet(reader.read_exact)
        init_reader = Reader(kexdh_init_payload)
        msg_type = init_reader.read_byte()
        assert msg_type == messages.SSH_MSG_KEXDH_INIT
        e = init_reader.read_mpint()

        y = 12345678901234567890123456789  # fixed, test-only "random" exponent
        f = pow(G, y, P)
        shared_secret = pow(e, y, P)

        public_key = host_key.public_key()
        host_key_blob = _rsa_host_key_blob(public_key)
        exchange_hash = compute_exchange_hash(
            client_version=client_version,
            server_version=server_version,
            client_kexinit_payload=client_kexinit_payload,
            server_kexinit_payload=server_kexinit_payload,
            host_key_blob=host_key_blob,
            e=e,
            f=f,
            shared_secret=shared_secret,
            hash_name="sha1",
        )
        raw_signature = host_key.sign(exchange_hash, padding.PKCS1v15(), hashes.SHA1())
        signature_blob = encode_string(b"ssh-rsa") + encode_string(raw_signature)

        reply_payload = (
            bytes([messages.SSH_MSG_KEXDH_REPLY])
            + encode_string(host_key_blob)
            + encode_mpint(f)
            + encode_string(signature_blob)
        )
        conn.sendall(encode_binary_packet(reply_payload))

        decode_binary_packet(reader.read_exact)  # client's NEWKEYS
        conn.sendall(encode_binary_packet(bytes([messages.SSH_MSG_NEWKEYS])))

        session_id = exchange_hash
        session_keys = derive_session_keys(
            shared_secret,
            exchange_hash,
            session_id,
            hash_name="sha1",
            mac_key_length_client_to_server=20,
            mac_key_length_server_to_client=20,
        )
        PACKETS_BEFORE_ENCRYPTION = 3
        server_incoming = SSHSessionCipher(
            session_keys.enc_key_client_to_server,
            session_keys.iv_client_to_server,
            session_keys.mac_key_client_to_server,
            initial_seq=PACKETS_BEFORE_ENCRYPTION,
            mac_algorithm="hmac-sha1",
        )
        server_outgoing = SSHSessionCipher(
            session_keys.enc_key_server_to_client,
            session_keys.iv_server_to_client,
            session_keys.mac_key_server_to_client,
            initial_seq=PACKETS_BEFORE_ENCRYPTION,
            mac_algorithm="hmac-sha1",
        )

        request = server_incoming.decode_packet(reader.read_exact)
        request_reader = Reader(request)
        assert request_reader.read_byte() == messages.SSH_MSG_SERVICE_REQUEST
        service_name = request_reader.read_string()

        response = bytes([messages.SSH_MSG_SERVICE_ACCEPT]) + encode_string(service_name)
        conn.sendall(server_outgoing.encode_packet(response))
    except OSError:
        pass
    finally:
        conn.close()


@dataclass
class LegacySSHServerHandle:
    host: str
    port: int
    thread: threading.Thread
    _server_socket: socket.socket

    def stop(self) -> None:
        self._server_socket.close()
        self.thread.join(timeout=2.0)


def start_legacy_ssh_server() -> LegacySSHServerHandle:
    host_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(1)
    host, port = server_socket.getsockname()

    def _serve() -> None:
        while True:
            try:
                conn, _ = server_socket.accept()
            except OSError:
                return
            threading.Thread(target=_serve_one_connection, args=(conn, host_key), daemon=True).start()

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()

    return LegacySSHServerHandle(host=host, port=port, thread=thread, _server_socket=server_socket)
