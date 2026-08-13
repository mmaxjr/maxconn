"""Full SSH key-exchange handshake: version exchange through NEWKEYS,
producing an established encrypted session ready for authentication
(RFC 4253 sections 4.2, 7, and 8)."""

from __future__ import annotations

import socket
from dataclasses import dataclass

from maxconn.exceptions import ProtocolError
from maxconn.transport.ssh import messages
from maxconn.transport.ssh.diffie_hellman import perform_diffie_hellman, perform_ecdh_nistp256
from maxconn.transport.ssh.handshake import recv_version, send_version
from maxconn.transport.ssh.hostkey import verify_host_key_signature
from maxconn.transport.ssh.kex import (
    ENCRYPTION_ALGORITHMS,
    KEX_ALGORITHMS,
    MAC_ALGORITHMS,
    SERVER_HOST_KEY_ALGORITHMS,
    build_kexinit,
    negotiate,
    parse_kexinit,
)
from maxconn.transport.ssh.keys import derive_session_keys
from maxconn.transport.ssh.packet import decode_binary_packet, encode_binary_packet
from maxconn.transport.ssh.session import SSHSessionCipher
from maxconn.transport.ssh.socket_reader import SocketReader


@dataclass
class EncryptedSession:
    reader: SocketReader
    sock: socket.socket
    outgoing: SSHSessionCipher
    incoming: SSHSessionCipher
    session_id: bytes
    host_key_blob: bytes

    def send_message(self, payload: bytes) -> None:
        self.sock.sendall(self.outgoing.encode_packet(payload))

    def recv_message(self) -> bytes:
        return self.incoming.decode_packet(self.reader.read_exact)


def establish_encrypted_session(sock: socket.socket) -> EncryptedSession:
    reader = SocketReader(sock)

    client_version = send_version(sock)
    server_version = recv_version(reader)

    client_kexinit_payload = build_kexinit()
    sock.sendall(encode_binary_packet(client_kexinit_payload))
    server_kexinit_payload = decode_binary_packet(reader.read_exact)
    server_kexinit = parse_kexinit(server_kexinit_payload)

    kex_algorithm = negotiate(KEX_ALGORITHMS, server_kexinit.kex_algorithms, "key exchange")
    negotiate(SERVER_HOST_KEY_ALGORITHMS, server_kexinit.server_host_key_algorithms, "server host key")
    negotiate(
        ENCRYPTION_ALGORITHMS,
        server_kexinit.encryption_algorithms_client_to_server,
        "client-to-server encryption",
    )
    negotiate(
        ENCRYPTION_ALGORITHMS,
        server_kexinit.encryption_algorithms_server_to_client,
        "server-to-client encryption",
    )
    mac_algorithm = negotiate(MAC_ALGORITHMS, server_kexinit.mac_algorithms_client_to_server, "client-to-server MAC")
    negotiate(MAC_ALGORITHMS, server_kexinit.mac_algorithms_server_to_client, "server-to-client MAC")

    if kex_algorithm == "ecdh-sha2-nistp256":
        dh_result = perform_ecdh_nistp256(
            sock,
            reader,
            client_version=client_version,
            server_version=server_version,
            client_kexinit_payload=client_kexinit_payload,
            server_kexinit_payload=server_kexinit_payload,
        )
    else:
        dh_result = perform_diffie_hellman(
            sock,
            reader,
            client_version=client_version,
            server_version=server_version,
            client_kexinit_payload=client_kexinit_payload,
            server_kexinit_payload=server_kexinit_payload,
            hash_name="sha1" if kex_algorithm == "diffie-hellman-group14-sha1" else "sha256",
        )
    verify_host_key_signature(dh_result.host_key_blob, dh_result.signature_blob, dh_result.exchange_hash)

    # We only ever do one key exchange (no rekeying), so session_id is just
    # this exchange's hash - RFC 4253 §7.2.
    session_id = dh_result.exchange_hash
    session_keys = derive_session_keys(
        dh_result.shared_secret,
        dh_result.exchange_hash,
        session_id,
        mac_key_length=20 if mac_algorithm == "hmac-sha1" else 32,
    )

    # Each side has already sent exactly 3 plaintext packets by this point
    # (KEXINIT, KEXDH_INIT/REPLY, and NEWKEYS itself), and the SSH sequence
    # number counts those too - RFC 4253 §6.4.
    PACKETS_BEFORE_ENCRYPTION = 3

    sock.sendall(encode_binary_packet(bytes([messages.SSH_MSG_NEWKEYS])))
    outgoing = SSHSessionCipher(
        session_keys.enc_key_client_to_server,
        session_keys.iv_client_to_server,
        session_keys.mac_key_client_to_server,
        initial_seq=PACKETS_BEFORE_ENCRYPTION,
        mac_algorithm=mac_algorithm,
    )

    server_newkeys_payload = decode_binary_packet(reader.read_exact)
    if server_newkeys_payload[:1] != bytes([messages.SSH_MSG_NEWKEYS]):
        got = server_newkeys_payload[0] if server_newkeys_payload else None
        raise ProtocolError(f"Expected SSH_MSG_NEWKEYS ({messages.SSH_MSG_NEWKEYS}), got {got}")
    incoming = SSHSessionCipher(
        session_keys.enc_key_server_to_client,
        session_keys.iv_server_to_client,
        session_keys.mac_key_server_to_client,
        initial_seq=PACKETS_BEFORE_ENCRYPTION,
        mac_algorithm=mac_algorithm,
    )

    return EncryptedSession(
        reader=reader,
        sock=sock,
        outgoing=outgoing,
        incoming=incoming,
        session_id=session_id,
        host_key_blob=dh_result.host_key_blob,
    )
