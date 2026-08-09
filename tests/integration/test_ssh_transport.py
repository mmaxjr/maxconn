import pytest

from maxconn.exceptions import AuthenticationError, ConnectionTimeoutError
from maxconn.transport.ssh.transport import SSHTransport


def test_connect_authenticate_send_recv_close(ssh_server):
    transport = SSHTransport()
    transport.connect(ssh_server.host, ssh_server.port, timeout=5.0)
    transport.authenticate(ssh_server.username, password=ssh_server.password)

    banner = b""
    while b"device>" not in banner:
        banner += transport.recv(timeout=5.0)
    assert b"Welcome" in banner

    transport.send("show status\n")
    reply = b""
    while b"device>" not in reply:
        reply += transport.recv(timeout=5.0)
    assert b"echo:show status" in reply

    transport.close()


def test_authenticate_with_wrong_password_raises_authentication_error(ssh_server):
    transport = SSHTransport()
    transport.connect(ssh_server.host, ssh_server.port, timeout=5.0)
    with pytest.raises(AuthenticationError):
        transport.authenticate(ssh_server.username, password="wrong-password")
    transport.close()


def test_authenticate_with_publickey(ssh_server):
    transport = SSHTransport()
    transport.connect(ssh_server.host, ssh_server.port, timeout=5.0)
    transport.authenticate(ssh_server.username, pkey=ssh_server.client_key.key)  # must not raise
    transport.close()


def test_connect_to_closed_port_raises_connection_timeout_error():
    transport = SSHTransport()
    with pytest.raises(ConnectionTimeoutError):
        transport.connect("127.0.0.1", 1, timeout=1.0)
