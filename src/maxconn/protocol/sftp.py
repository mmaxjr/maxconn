from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from maxconn.exceptions import ProtocolError

SSH_FXP_INIT = 1
SSH_FXP_VERSION = 2
SSH_FXP_OPEN = 3
SSH_FXP_CLOSE = 4
SSH_FXP_READ = 5
SSH_FXP_WRITE = 6
SSH_FXP_OPENDIR = 11
SSH_FXP_READDIR = 12
SSH_FXP_STATUS = 101
SSH_FXP_HANDLE = 102
SSH_FXP_DATA = 103
SSH_FXP_NAME = 104

SSH_FX_OK = 0
SSH_FX_EOF = 1

SSH_FXF_READ = 0x00000001
SSH_FXF_WRITE = 0x00000002
SSH_FXF_CREAT = 0x00000008
SSH_FXF_TRUNC = 0x00000010

READ_SIZE = 32768


class SFTPChannel(Protocol):
    def send_data(self, data: bytes) -> None: ...

    def recv_data(self) -> bytes: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class SFTPName:
    filename: str
    longname: str


class SFTPClient:
    def __init__(self, channel: SFTPChannel) -> None:
        self._channel = channel
        self._recv_buffer = b""
        self._next_request_id = 1
        self.server_version = self._init()

    def _init(self) -> int:
        self._send_packet(bytes([SSH_FXP_INIT]) + struct.pack(">I", 3))
        payload = self._recv_packet()
        msg_type = payload[0]
        if msg_type != SSH_FXP_VERSION:
            raise ProtocolError(f"Expected SFTP VERSION, got message {msg_type}")
        return struct.unpack(">I", payload[1:5])[0]

    def listdir(self, path: str) -> list[str]:
        handle = self._open_dir(path)
        names: list[str] = []
        try:
            while True:
                request_id = self._request_id()
                self._send_request(SSH_FXP_READDIR, request_id, _encode_string(handle))
                payload = self._recv_packet()
                msg_type = payload[0]
                if msg_type == SSH_FXP_STATUS:
                    code = _read_uint32(payload, 5)
                    if code == SSH_FX_EOF:
                        break
                    self._raise_status(payload)
                if msg_type != SSH_FXP_NAME:
                    raise ProtocolError(f"Expected SFTP NAME, got message {msg_type}")
                names.extend(name.filename for name in _parse_names(payload[5:]))
        finally:
            self._close_handle(handle)
        return names

    def download(self, remote_path: str, local_path: str | Path) -> None:
        handle = self._open_file(remote_path, SSH_FXF_READ)
        offset = 0
        target = Path(local_path)
        try:
            with target.open("wb") as output:
                while True:
                    request_id = self._request_id()
                    payload = _encode_string(handle) + struct.pack(">QI", offset, READ_SIZE)
                    self._send_request(SSH_FXP_READ, request_id, payload)
                    response = self._recv_packet()
                    msg_type = response[0]
                    if msg_type == SSH_FXP_STATUS:
                        code = _read_uint32(response, 5)
                        if code == SSH_FX_EOF:
                            break
                        self._raise_status(response)
                    if msg_type != SSH_FXP_DATA:
                        raise ProtocolError(f"Expected SFTP DATA, got message {msg_type}")
                    data, _ = _read_string(response, 5)
                    if not data:
                        break
                    output.write(data)
                    offset += len(data)
        finally:
            self._close_handle(handle)

    def upload(self, local_path: str | Path, remote_path: str) -> None:
        handle = self._open_file(remote_path, SSH_FXF_WRITE | SSH_FXF_CREAT | SSH_FXF_TRUNC)
        offset = 0
        source = Path(local_path)
        try:
            with source.open("rb") as input_file:
                while True:
                    chunk = input_file.read(READ_SIZE)
                    if not chunk:
                        break
                    request_id = self._request_id()
                    payload = _encode_string(handle) + struct.pack(">Q", offset) + _encode_string(chunk)
                    self._send_request(SSH_FXP_WRITE, request_id, payload)
                    self._expect_ok(request_id)
                    offset += len(chunk)
        finally:
            self._close_handle(handle)

    def close(self) -> None:
        self._channel.close()

    def _open_dir(self, path: str) -> bytes:
        request_id = self._request_id()
        self._send_request(SSH_FXP_OPENDIR, request_id, _encode_string(path.encode()))
        return self._read_handle(request_id)

    def _open_file(self, path: str, pflags: int) -> bytes:
        request_id = self._request_id()
        attrs = struct.pack(">I", 0)
        payload = _encode_string(path.encode()) + struct.pack(">I", pflags) + attrs
        self._send_request(SSH_FXP_OPEN, request_id, payload)
        return self._read_handle(request_id)

    def _read_handle(self, request_id: int) -> bytes:
        payload = self._recv_packet()
        if payload[0] == SSH_FXP_STATUS:
            self._raise_status(payload)
        if payload[0] != SSH_FXP_HANDLE:
            raise ProtocolError(f"Expected SFTP HANDLE, got message {payload[0]}")
        response_id = _read_uint32(payload, 1)
        if response_id != request_id:
            raise ProtocolError(f"Unexpected SFTP response id {response_id}, expected {request_id}")
        handle, _ = _read_string(payload, 5)
        return handle

    def _close_handle(self, handle: bytes) -> None:
        request_id = self._request_id()
        self._send_request(SSH_FXP_CLOSE, request_id, _encode_string(handle))
        self._expect_ok(request_id)

    def _expect_ok(self, request_id: int) -> None:
        payload = self._recv_packet()
        if payload[0] != SSH_FXP_STATUS:
            raise ProtocolError(f"Expected SFTP STATUS, got message {payload[0]}")
        response_id = _read_uint32(payload, 1)
        if response_id != request_id:
            raise ProtocolError(f"Unexpected SFTP response id {response_id}, expected {request_id}")
        code = _read_uint32(payload, 5)
        if code != SSH_FX_OK:
            self._raise_status(payload)

    def _raise_status(self, payload: bytes) -> None:
        code = _read_uint32(payload, 5)
        message, _ = _read_string(payload, 9)
        text = message.decode(errors="replace") or f"SFTP status {code}"
        raise ProtocolError(text)

    def _send_request(self, msg_type: int, request_id: int, payload: bytes) -> None:
        self._send_packet(bytes([msg_type]) + struct.pack(">I", request_id) + payload)

    def _request_id(self) -> int:
        request_id = self._next_request_id
        self._next_request_id += 1
        return request_id

    def _send_packet(self, payload: bytes) -> None:
        self._channel.send_data(struct.pack(">I", len(payload)) + payload)

    def _recv_packet(self) -> bytes:
        header = self._recv_exact(4)
        length = struct.unpack(">I", header)[0]
        return self._recv_exact(length)

    def _recv_exact(self, size: int) -> bytes:
        chunks: list[bytes] = []
        remaining = size
        while remaining:
            if self._recv_buffer:
                chunk = self._recv_buffer
                self._recv_buffer = b""
            else:
                chunk = self._channel.recv_data()
            if not chunk:
                raise ProtocolError("SFTP channel closed while reading packet")
            chunks.append(chunk[:remaining])
            self._recv_buffer = chunk[remaining:]
            remaining -= len(chunks[-1])
        return b"".join(chunks)


def _parse_names(payload: bytes) -> list[SFTPName]:
    count = _read_uint32(payload, 0)
    offset = 4
    names: list[SFTPName] = []
    for _ in range(count):
        filename, offset = _read_string(payload, offset)
        longname, offset = _read_string(payload, offset)
        attrs_flags = _read_uint32(payload, offset)
        offset += 4
        offset = _skip_attrs(payload, offset, attrs_flags)
        names.append(
            SFTPName(
                filename=filename.decode(errors="replace"),
                longname=longname.decode(errors="replace"),
            )
        )
    return names


def _skip_attrs(payload: bytes, offset: int, flags: int) -> int:
    if flags & 0x00000001:
        offset += 8
    if flags & 0x00000002:
        offset += 8
    if flags & 0x00000004:
        offset += 4
    if flags & 0x00000008:
        offset += 8
    if flags & 0x80000000:
        count = _read_uint32(payload, offset)
        offset += 4
        for _ in range(count * 2):
            _, offset = _read_string(payload, offset)
    return offset


def _encode_string(value: bytes) -> bytes:
    return struct.pack(">I", len(value)) + value


def _read_string(payload: bytes, offset: int) -> tuple[bytes, int]:
    size = _read_uint32(payload, offset)
    offset += 4
    return payload[offset : offset + size], offset + size


def _read_uint32(payload: bytes, offset: int) -> int:
    return struct.unpack(">I", payload[offset : offset + 4])[0]


def connect_sftp(
    host: str,
    *,
    username: str,
    password: str | None = None,
    pkey: object | None = None,
    port: int = 22,
    timeout: float = 10.0,
) -> SFTPClient:
    from maxconn.transport.ssh.transport import SSHTransport

    transport = SSHTransport()
    transport.connect(host, port=port, timeout=timeout)
    try:
        transport.authenticate(
            username=username,
            password=password,
            pkey=pkey,
            timeout=timeout,
            open_shell=False,
        )
        channel = transport.open_sftp_channel()
        return SFTPClient(_TransportBackedSFTPChannel(transport, channel))
    except Exception:
        transport.close()
        raise


class _TransportBackedSFTPChannel:
    def __init__(self, transport: object, channel: SFTPChannel) -> None:
        self._transport = transport
        self._channel = channel

    def send_data(self, data: bytes) -> None:
        self._channel.send_data(data)

    def recv_data(self) -> bytes:
        return self._channel.recv_data()

    def close(self) -> None:
        self._channel.close()
        self._transport.close()
