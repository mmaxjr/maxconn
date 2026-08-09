import pytest

import maxconn


def test_connect_over_telnet_and_run_command(telnet_server):
    with maxconn.connect(
        telnet_server.host,
        protocol="telnet",
        username=telnet_server.username,
        password=telnet_server.password,
        port=telnet_server.port,
        timeout=5.0,
    ) as conn:
        output = conn.send_command("show version", read_timeout=3.0)

    assert "echo:show version" in output


def test_connect_with_unsupported_protocol_raises_value_error(telnet_server):
    with pytest.raises(ValueError):
        maxconn.connect(
            telnet_server.host,
            protocol="carrier-pigeon",
            username="x",
            port=telnet_server.port,
        )
