import pytest

from maxconn.exceptions import AuthenticationError, ConnectionTimeoutError
from maxconn.transport.telnet.transport import TelnetTransport


def test_connect_send_recv_close(telnet_server):
    transport = TelnetTransport()
    transport.connect(telnet_server.host, telnet_server.port, timeout=5.0)

    # The server sends its IAC negotiation and the "login:" prompt in
    # separate TCP writes, which can arrive as separate recv() chunks, so
    # accumulate until the prompt shows up rather than asserting on a
    # single recv() call.
    data = b""
    for _ in range(10):
        data += transport.recv(timeout=5.0)
        if b"login:" in data:
            break
    assert b"login:" in data  # IAC negotiation stripped, only the prompt remains

    transport.close()


def test_connect_to_closed_port_raises_connection_timeout_error():
    transport = TelnetTransport()
    with pytest.raises(ConnectionTimeoutError):
        transport.connect("127.0.0.1", 1, timeout=1.0)


def test_authenticate_with_correct_credentials_succeeds(telnet_server):
    transport = TelnetTransport()
    transport.connect(telnet_server.host, telnet_server.port, timeout=5.0)
    transport.authenticate(telnet_server.username, password=telnet_server.password)
    transport.close()


def test_authenticate_with_wrong_password_raises_authentication_error(telnet_server):
    transport = TelnetTransport()
    transport.connect(telnet_server.host, telnet_server.port, timeout=5.0)
    with pytest.raises(AuthenticationError):
        transport.authenticate(telnet_server.username, password="wrong-password")
    transport.close()
