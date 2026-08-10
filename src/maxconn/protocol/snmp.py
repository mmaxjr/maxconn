from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Any

GET_REQUEST = 0xA0
GET_NEXT_REQUEST = 0xA1
GET_RESPONSE = 0xA2


@dataclass(frozen=True)
class SNMPResult:
    oid: str
    value: Any


class SNMPClient:
    def __init__(
        self,
        host: str,
        *,
        community: str = "public",
        port: int = 161,
        timeout: float = 2.0,
    ) -> None:
        self.host = host
        self.community = community
        self.port = port
        self.timeout = timeout
        self._request_id = 1

    def get(self, oid: str) -> SNMPResult:
        return self._request(GET_REQUEST, oid)

    def getnext(self, oid: str) -> SNMPResult:
        return self._request(GET_NEXT_REQUEST, oid)

    def walk(self, oid: str, *, limit: int = 100) -> list[SNMPResult]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        prefix = oid.rstrip(".")
        current = prefix
        results: list[SNMPResult] = []
        for _ in range(limit):
            result = self.getnext(current)
            if not _is_in_subtree(result.oid, prefix):
                break
            results.append(result)
            current = result.oid
        return results

    def _request(self, pdu_type: int, oid: str) -> SNMPResult:
        request_id = self._request_id
        self._request_id += 1
        packet = _message(
            community=self.community,
            pdu_type=pdu_type,
            request_id=request_id,
            oid=oid,
        )
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(self.timeout)
            sock.sendto(packet, (self.host, self.port))
            response, _addr = sock.recvfrom(65535)
        finally:
            sock.close()
        return _parse_response(response)


def _message(*, community: str, pdu_type: int, request_id: int, oid: str) -> bytes:
    varbind = _seq(_oid(oid) + _null())
    varbinds = _seq(varbind)
    pdu = bytes([pdu_type]) + _length(_int(request_id) + _int(0) + _int(0) + varbinds)
    return _seq(_int(1) + _octet(community.encode()) + pdu)


def _parse_response(data: bytes) -> SNMPResult:
    message = _Reader(data).read_sequence(0x30)
    message.read_tlv(0x02)
    message.read_tlv(0x04)
    pdu = message.read_sequence(GET_RESPONSE)
    pdu.read_tlv(0x02)
    error_status = _decode_int(pdu.read_tlv(0x02))
    pdu.read_tlv(0x02)
    if error_status:
        raise ValueError(f"SNMP error status {error_status}")
    varbinds = pdu.read_sequence(0x30)
    varbind = varbinds.read_sequence(0x30)
    oid = _decode_oid(varbind.read_tlv(0x06))
    value_type, value_raw = varbind.read_any()
    return SNMPResult(oid=oid, value=_decode_value(value_type, value_raw))


def _decode_value(value_type: int, raw: bytes) -> Any:
    if value_type == 0x02:
        return _decode_int(raw)
    if value_type == 0x04:
        try:
            return raw.decode()
        except UnicodeDecodeError:
            return raw
    if value_type == 0x05:
        return None
    if value_type in {0x40, 0x41, 0x42, 0x43, 0x46}:
        return int.from_bytes(raw, "big")
    return raw


def _seq(content: bytes) -> bytes:
    return bytes([0x30]) + _length(content) + content


def _int(value: int) -> bytes:
    if value == 0:
        raw = b"\x00"
    else:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        if raw[0] & 0x80:
            raw = b"\x00" + raw
    return bytes([0x02]) + _length(raw) + raw


def _octet(value: bytes) -> bytes:
    return bytes([0x04]) + _length(value) + value


def _null() -> bytes:
    return b"\x05\x00"


def _oid(oid: str) -> bytes:
    parts = [int(part) for part in oid.split(".")]
    if len(parts) < 2:
        raise ValueError("OID must contain at least two arcs")
    encoded = bytes([parts[0] * 40 + parts[1]])
    for part in parts[2:]:
        encoded += _base128(part)
    return bytes([0x06]) + _length(encoded) + encoded


def _base128(value: int) -> bytes:
    stack = [value & 0x7F]
    value >>= 7
    while value:
        stack.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(stack))


def _length(content: bytes) -> bytes:
    size = len(content)
    if size < 128:
        return bytes([size])
    raw = size.to_bytes((size.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def _decode_int(raw: bytes) -> int:
    return int.from_bytes(raw, "big", signed=bool(raw and raw[0] & 0x80))


def _decode_oid(raw: bytes) -> str:
    if not raw:
        raise ValueError("empty OID")
    parts = [raw[0] // 40, raw[0] % 40]
    value = 0
    for byte in raw[1:]:
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            parts.append(value)
            value = 0
    return ".".join(str(part) for part in parts)


def _is_in_subtree(oid: str, prefix: str) -> bool:
    return oid == prefix or oid.startswith(prefix + ".")


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def read_any(self) -> tuple[int, bytes]:
        value_type = self._read_byte()
        size = self._read_length()
        value = self.data[self.pos : self.pos + size]
        self.pos += size
        return value_type, value

    def read_tlv(self, expected: int) -> bytes:
        value_type, value = self.read_any()
        if value_type != expected:
            raise ValueError(f"expected tag {expected:#x}, got {value_type:#x}")
        return value

    def read_sequence(self, expected: int) -> _Reader:
        return _Reader(self.read_tlv(expected))

    def _read_byte(self) -> int:
        value = self.data[self.pos]
        self.pos += 1
        return value

    def _read_length(self) -> int:
        first = self._read_byte()
        if first < 128:
            return first
        count = first & 0x7F
        raw = self.data[self.pos : self.pos + count]
        self.pos += count
        return int.from_bytes(raw, "big")
