from __future__ import annotations

import pytest

import maxconn
from maxconn.exceptions import AuthenticationError


class _FakeTransport:
    """Records connect()/close() calls and fails authenticate(), to prove
    maxconn.connect() cleans up the transport when auth fails."""

    def __init__(self) -> None:
        self.connected = False
        self.closed = False

    def connect(self, host, port, timeout):
        self.connected = True

    def authenticate(self, username, *, password=None, pkey=None, timeout=None):
        raise AuthenticationError("simulated: wrong credentials")

    def close(self) -> None:
        self.closed = True


def test_connect_closes_the_transport_when_authentication_fails(monkeypatch):
    fake = _FakeTransport()
    monkeypatch.setattr("maxconn.transport.telnet.transport.TelnetTransport", lambda: fake)

    with pytest.raises(AuthenticationError):
        maxconn.connect("10.0.0.1", protocol="telnet", username="admin", password="wrong")

    assert fake.connected is True
    assert fake.closed is True
