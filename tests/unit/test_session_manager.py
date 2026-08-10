from maxconn.sessions import SessionManager


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


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
