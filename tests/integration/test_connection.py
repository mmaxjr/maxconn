from maxconn.transport.base import Connection
from maxconn.transport.telnet.transport import TelnetTransport


def test_connection_send_command_returns_device_output(telnet_server):
    transport = TelnetTransport()
    transport.connect(telnet_server.host, telnet_server.port, timeout=5.0)
    transport.authenticate(telnet_server.username, password=telnet_server.password)

    with Connection(transport) as conn:
        output = conn.send_command("show status", read_timeout=3.0)

    assert "echo:show status" in output


def test_connection_read_until_matches_marker(telnet_server):
    transport = TelnetTransport()
    transport.connect(telnet_server.host, telnet_server.port, timeout=5.0)

    conn = Connection(transport)
    banner = conn.read_until("login:", timeout=5.0)
    assert "login:" in banner
    conn.close()
