import pytest

from maxconn.automation import ExpectSession
from maxconn.exceptions import ConnectionTimeoutError


class FakeConnection:
    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.sent = []

    def send(self, data):
        self.sent.append(data)

    def recv(self, timeout=None):
        if not self._chunks:
            raise ConnectionTimeoutError("no more data")
        chunk = self._chunks.pop(0)
        return chunk.encode()


def test_run_sends_command_and_reads_until_prompt():
    conn = FakeConnection(["show status\r\nok\r\nrouter#"])
    expect = ExpectSession(conn, prompt_markers=("#",))

    output = expect.run("show status", timeout=1.0)

    assert conn.sent == ["show status\n"]
    assert output == "show status\r\nok\r\nrouter#"


def test_run_strips_command_echo_when_requested():
    conn = FakeConnection(["display version\r\nVRP software\r\nOLT>"])
    expect = ExpectSession(conn, prompt_markers=(">",))

    output = expect.run("display version", timeout=1.0, strip_echo=True)

    assert output == "VRP software\r\nOLT>"


def test_run_answers_pagination_markers_and_removes_them_from_output():
    conn = FakeConnection(["line 1\r\n--More--", "line 2\r\nOLT>"])
    expect = ExpectSession(conn, prompt_markers=(">",), pagination_markers=("--More--",))

    output = expect.run("display current", timeout=1.0)

    assert conn.sent == ["display current\n", " "]
    assert output == "line 1\r\nline 2\r\nOLT>"


def test_run_times_out_with_partial_output_when_prompt_is_missing():
    conn = FakeConnection(["partial output"])
    expect = ExpectSession(conn, prompt_markers=("#",))

    with pytest.raises(ConnectionTimeoutError, match="partial output"):
        expect.run("show status", timeout=1.0)
