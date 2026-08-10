from __future__ import annotations

import socket

from maxconn.protocol.snmp import SNMPClient


class FakeUDPSocket:
    def __init__(self, responses: list[bytes]) -> None:
        self.responses = responses
        self.sent: list[bytes] = []
        self.timeout: float | None = None

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
        self.sent.append(data)

    def recvfrom(self, size: int) -> tuple[bytes, tuple[str, int]]:
        return self.responses.pop(0), ("127.0.0.1", 161)

    def close(self) -> None:
        pass


def test_snmp_get_returns_oid_and_value(monkeypatch):
    fake = FakeUDPSocket([_response("1.3.6.1.2.1.1.5.0", b"router-01")])
    monkeypatch.setattr(socket, "socket", lambda family, type: fake)

    result = SNMPClient("127.0.0.1", community="public", timeout=1.0).get(
        "1.3.6.1.2.1.1.5.0"
    )

    assert result.oid == "1.3.6.1.2.1.1.5.0"
    assert result.value == "router-01"
    assert fake.timeout == 1.0
    assert fake.sent


def test_snmp_walk_uses_getnext_until_oid_leaves_prefix(monkeypatch):
    fake = FakeUDPSocket(
        [
            _response("1.3.6.1.2.1.1.1.0", b"description"),
            _response("1.3.6.1.2.1.1.5.0", b"router-01"),
            _response("1.3.6.1.2.1.2.1.0", b"outside"),
        ]
    )
    monkeypatch.setattr(socket, "socket", lambda family, type: fake)

    results = SNMPClient("127.0.0.1", community="public", timeout=1.0).walk(
        "1.3.6.1.2.1.1",
        limit=10,
    )

    assert [(item.oid, item.value) for item in results] == [
        ("1.3.6.1.2.1.1.1.0", "description"),
        ("1.3.6.1.2.1.1.5.0", "router-01"),
    ]
    assert len(fake.sent) == 3


def _response(oid: str, value: bytes) -> bytes:
    varbind = _seq(_oid(oid) + _octet(value))
    varbinds = _seq(varbind)
    content = _int(1) + _int(0) + _int(0) + varbinds
    pdu = bytes([0xA2]) + _length(content) + content
    return _seq(_int(1) + _octet(b"public") + pdu)


def _seq(content: bytes) -> bytes:
    return bytes([0x30]) + _length(content) + content


def _int(value: int) -> bytes:
    return bytes([0x02, 0x01, value])


def _octet(value: bytes) -> bytes:
    return bytes([0x04]) + _length(value) + value


def _oid(oid: str) -> bytes:
    parts = [int(part) for part in oid.split(".")]
    encoded = bytes([parts[0] * 40 + parts[1]])
    for part in parts[2:]:
        stack = [part & 0x7F]
        part >>= 7
        while part:
            stack.append(0x80 | (part & 0x7F))
            part >>= 7
        encoded += bytes(reversed(stack))
    return bytes([0x06]) + _length(encoded) + encoded


def _length(content: bytes) -> bytes:
    size = len(content)
    if size < 128:
        return bytes([size])
    raw = size.to_bytes((size.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw
