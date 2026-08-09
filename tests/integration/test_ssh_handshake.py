import socket

from maxconn.transport.ssh.handshake import recv_version, send_version
from maxconn.transport.ssh.socket_reader import SocketReader


def test_version_exchange_against_real_ssh_server(ssh_server):
    sock = socket.create_connection((ssh_server.host, ssh_server.port), timeout=5.0)
    reader = SocketReader(sock)
    try:
        send_version(sock)
        server_banner = recv_version(reader)
    finally:
        sock.close()

    assert server_banner.startswith(b"SSH-2.0-")
