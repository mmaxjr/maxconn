import socket

from maxconn.transport.ssh.diffie_hellman import perform_diffie_hellman
from maxconn.transport.ssh.handshake import recv_version, send_version
from maxconn.transport.ssh.kex import build_kexinit
from maxconn.transport.ssh.packet import decode_binary_packet, encode_binary_packet
from maxconn.transport.ssh.socket_reader import SocketReader


def test_diffie_hellman_exchange_against_real_ssh_server(ssh_server):
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

    assert isinstance(result.shared_secret, int)
    assert result.shared_secret > 0
    assert len(result.exchange_hash) == 32
    assert len(result.host_key_blob) > 0
    assert len(result.signature_blob) > 0
