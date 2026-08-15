import pytest

from maxconn.sessions import SessionManager


class FakeConnection:
    def __init__(self, *, fail_close: bool = False):
        self.closed = False
        self._fail_close = fail_close

    def close(self):
        if self._fail_close:
            raise ConnectionError("simulated: peer already reset the connection")
        self.closed = True


def test_close_all_still_closes_every_session_even_if_one_fails(monkeypatch):
    # Regression: close_all() used to stop at the first exception, leaking
    # every session after the one that failed to close cleanly.
    manager = SessionManager()
    good_first = FakeConnection()
    bad = FakeConnection(fail_close=True)
    good_last = FakeConnection()
    manager.add("a", good_first, host="10.0.0.1")
    manager.add("b", bad, host="10.0.0.2")
    manager.add("c", good_last, host="10.0.0.3")

    with pytest.raises(ConnectionError):
        manager.close_all()

    assert good_first.closed is True
    assert good_last.closed is True
    assert manager.names() == []


def test_add_closes_the_previous_connection_when_reusing_a_name():
    # Regression: add()/connect() silently overwrote an existing session
    # entry without closing the connection it replaced, leaking it.
    manager = SessionManager()
    old_conn = FakeConnection()
    new_conn = FakeConnection()
    manager.add("core1", old_conn, host="10.0.0.1")

    manager.add("core1", new_conn, host="10.0.0.2")

    assert old_conn.closed is True
    assert manager.get("core1") is new_conn


def test_session_manager_add_get_and_close_all():
    manager = SessionManager(defaults={"protocol": "ssh", "username": "admin"})
    conn = FakeConnection()

    manager.add("olt-01", conn, host="192.0.2.10")

    assert manager.get("olt-01") is conn
    assert manager.names() == ["olt-01"]
    assert manager.defaults["protocol"] == "ssh"

    manager.close_all()

    assert conn.closed is True
    assert manager.names() == []


def test_session_manager_connect_uses_shared_defaults(monkeypatch):
    calls = {}
    conn = FakeConnection()

    def fake_connect(host, **kwargs):
        calls["host"] = host
        calls["kwargs"] = kwargs
        return conn

    monkeypatch.setattr("maxconn.sessions.manager.maxconn.connect", fake_connect)
    manager = SessionManager(defaults={"protocol": "telnet", "username": "admin"})

    result = manager.connect("lab", "192.0.2.20", password="secret")

    assert result is conn
    assert manager.get("lab") is conn
    assert calls == {
        "host": "192.0.2.20",
        "kwargs": {"protocol": "telnet", "username": "admin", "password": "secret"},
    }
