import logging

import maxconn
from maxconn.automation import PromptProfile
from maxconn.transport.base import Connection


class FakeTransport:
    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.sent = []

    def connect(self, host, port, timeout):
        pass

    def authenticate(self, username, password=None, pkey=None, timeout=None):
        pass

    def send(self, data):
        self.sent.append(data)

    def recv(self, timeout=None):
        self.last_recv_timeout = timeout
        return self._chunks.pop(0)

    def close(self):
        pass


def test_connection_run_returns_structured_result():
    transport = FakeTransport([b"display version\r\nVRP\r\nOLT>"])
    conn = Connection(transport, host="192.0.2.10", protocol="telnet")

    result = conn.run("display version", prompt_markers=(">",), timeout=1.0)

    assert result.command == "display version"
    assert result.text == "VRP\r\nOLT>"
    assert result.bytes == b"VRP\r\nOLT>"
    assert result.exit_status is None
    assert result.ok is True
    assert result.elapsed >= 0
    assert transport.sent == ["display version\n"]


def test_connection_run_uses_prompt_profile_defaults():
    transport = FakeTransport([b"show status\r\nok\r\ndevice#"])
    conn = Connection(
        transport,
        host="192.0.2.10",
        protocol="ssh",
        prompt_profile=PromptProfile.CISCO,
    )

    result = conn.run("show status", timeout=1.0)

    assert result.text == "ok\r\ndevice#"


def test_connect_accepts_separate_timeout_arguments(monkeypatch):
    calls = {}

    class FakeTelnetTransport:
        def connect(self, host, port, timeout):
            calls["connect"] = (host, port, timeout)

        def authenticate(self, username, password=None, pkey=None, timeout=None):
            calls["auth"] = (username, password, pkey, timeout)

        def send(self, data):
            pass

        def recv(self, timeout=None):
            return b"device>"

        def close(self):
            pass

    monkeypatch.setattr(
        "maxconn.transport.telnet.transport.TelnetTransport",
        lambda: FakeTelnetTransport(),
    )

    conn = maxconn.connect(
        "192.0.2.10",
        protocol="telnet",
        username="admin",
        password="secret",
        connect_timeout=3.0,
        auth_timeout=4.0,
        command_timeout=5.0,
        prompt_timeout=6.0,
    )

    assert calls["connect"] == ("192.0.2.10", 23, 3.0)
    assert calls["auth"] == ("admin", "secret", None, 4.0)
    assert conn.command_timeout == 5.0
    assert conn.prompt_timeout == 6.0


def test_connection_run_logs_command_without_secrets(caplog):
    logger = logging.getLogger("maxconn.audit")
    logger.handlers = []
    logger.propagate = True
    transport = FakeTransport([b"configure password supersecret\r\nok\r\nOLT>"])
    conn = Connection(transport, host="192.0.2.10", protocol="telnet")

    with caplog.at_level(logging.INFO, logger="maxconn.audit"):
        conn.run("configure password supersecret", prompt_markers=(">",), timeout=1.0)

    messages = [record.getMessage() for record in caplog.records]
    assert any("command completed" in message for message in messages)
    assert any("configure password <redacted>" in message for message in messages)
    assert all("supersecret" not in message for message in messages)


def test_connection_recv_does_not_default_to_blocking_forever():
    # Regression: Connection.recv()/Transport.recv() defaulted to
    # timeout=None, which Python's socket API treats as "block forever,"
    # not "use a sensible default." Connection.recv()/.send() are
    # documented as public low-level escape hatches, so calling recv()
    # with no arguments against a device that stops responding used to
    # hang the calling thread with no way to recover.
    transport = FakeTransport([b"data"])
    conn = Connection(transport, host="192.0.2.10", protocol="telnet")

    conn.recv()

    assert transport.last_recv_timeout is not None
    assert transport.last_recv_timeout > 0


def test_connection_run_redacts_equals_sign_flag_form(caplog):
    # Regression: transport/base.py kept its own separate copy of the
    # secret-redaction regex, which was missing the same "--flag=value"
    # fix already applied to history.py's copy.
    logger = logging.getLogger("maxconn.audit")
    logger.handlers = []
    logger.propagate = True
    transport = FakeTransport([b"login --password=supersecret\r\nok\r\nOLT>"])
    conn = Connection(transport, host="192.0.2.10", protocol="telnet")

    with caplog.at_level(logging.INFO, logger="maxconn.audit"):
        conn.run("login --password=supersecret", prompt_markers=(">",), timeout=1.0)

    messages = [record.getMessage() for record in caplog.records]
    assert all("supersecret" not in message for message in messages)
