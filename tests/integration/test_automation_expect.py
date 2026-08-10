import maxconn
from maxconn.automation import ExpectSession


def test_expect_session_runs_command_over_telnet_connection(telnet_server):
    with maxconn.connect(
        telnet_server.host,
        protocol="telnet",
        username=telnet_server.username,
        password=telnet_server.password,
        port=telnet_server.port,
        timeout=5.0,
    ) as conn:
        expect = ExpectSession(conn, prompt_markers=("device> ",))

        output = expect.run("show status", timeout=3.0)

    assert "echo:show status" in output
    assert output.endswith("device> ")
