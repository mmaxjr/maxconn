import socket

from maxconn.transport.ssh.diffie_hellman import perform_diffie_hellman
from maxconn.transport.ssh.handshake import recv_version, send_version
from maxconn.transport.ssh.hostkey import verify_host_key_signature
from maxconn.transport.ssh.kex import build_kexinit
from maxconn.transport.ssh.packet import decode_binary_packet, encode_binary_packet
from maxconn.transport.ssh.socket_reader import SocketReader


def test_host_key_signature_verifies_against_real_ssh_server(ssh_server):
    """The strongest possible correctness check for the whole KEX pipeline:
    paramiko computes its own exchange hash independently (its own RFC 3526
    group14 prime, its own hashing) and signs it with the server's private
    key. If our exchange hash matches paramiko's, this signature verifies."""
    sock = socket.create_connection((ssh_server.host, ssh_server.port), timeout=5.0)
    reader = SocketReader(sock)
    try:
        client_version = send_version(sock)
        server_version = recv_version(reader)

        client_kexinit = build_kexinit(kex_algorithms=["diffie-hellman-group14-sha256"])
        sock.sendall(encode_binary_packet(client_kexinit))
        server_kexinit = decode_binary_packet(reader.read_exact)

        result = perform_diffie_hellman(
            sock,
            reader,
            client_version=client_version,
            server_version=server_version,
            client_kexinit_payload=client_kexinit,
            server_kexinit_payload=server_kexinit,
        )
    finally:
        sock.close()

    verify_host_key_signature(result.host_key_blob, result.signature_blob, result.exchange_hash)
