from __future__ import annotations

import struct

from maxconn.protocol.sftp import SFTPClient

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


class FakeSFTPChannel:
    def __init__(self, responses: list[bytes]) -> None:
        self.responses = responses
        self.sent: list[bytes] = []

    def send_data(self, data: bytes) -> None:
        self.sent.append(data)

    def recv_data(self) -> bytes:
        return self.responses.pop(0)

    def close(self) -> None:
        pass


def packet(payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + payload


def string(value: bytes) -> bytes:
    return struct.pack(">I", len(value)) + value


def status(request_id: int, code: int) -> bytes:
    return packet(
        bytes([SSH_FXP_STATUS])
        + struct.pack(">II", request_id, code)
        + string(b"")
        + string(b"")
    )


def test_sftp_client_sends_init_and_reads_server_version():
    channel = FakeSFTPChannel([packet(bytes([SSH_FXP_VERSION]) + struct.pack(">I", 3))])

    client = SFTPClient(channel)

    assert client.server_version == 3
    assert channel.sent == [packet(bytes([SSH_FXP_INIT]) + struct.pack(">I", 3))]


def test_sftp_listdir_reads_names_until_eof():
    channel = FakeSFTPChannel(
        [
            packet(bytes([SSH_FXP_VERSION]) + struct.pack(">I", 3)),
            packet(bytes([SSH_FXP_HANDLE]) + struct.pack(">I", 1) + string(b"H")),
            packet(
                bytes([SSH_FXP_NAME])
                + struct.pack(">II", 2, 2)
                + string(b"startup.cfg")
                + string(b"startup.cfg")
                + struct.pack(">I", 0)
                + string(b"backup.cfg")
                + string(b"backup.cfg")
                + struct.pack(">I", 0)
            ),
            status(3, SSH_FX_EOF),
            status(4, SSH_FX_OK),
        ]
    )
    client = SFTPClient(channel)

    names = client.listdir("/configs")

    assert names == ["startup.cfg", "backup.cfg"]
    assert channel.sent[1][4] == SSH_FXP_OPENDIR
    assert channel.sent[2][4] == SSH_FXP_READDIR
    assert channel.sent[3][4] == SSH_FXP_READDIR
    assert channel.sent[4][4] == SSH_FXP_CLOSE


def test_sftp_download_reads_file_until_eof(tmp_path):
    target = tmp_path / "startup.cfg"
    channel = FakeSFTPChannel(
        [
            packet(bytes([SSH_FXP_VERSION]) + struct.pack(">I", 3)),
            packet(bytes([SSH_FXP_HANDLE]) + struct.pack(">I", 1) + string(b"H")),
            packet(bytes([SSH_FXP_DATA]) + struct.pack(">I", 2) + string(b"line 1\n")),
            packet(bytes([SSH_FXP_DATA]) + struct.pack(">I", 3) + string(b"line 2\n")),
            status(4, SSH_FX_EOF),
            status(5, SSH_FX_OK),
        ]
    )
    client = SFTPClient(channel)

    client.download("/remote/startup.cfg", target)

    assert target.read_text() == "line 1\nline 2\n"
    assert channel.sent[1][4] == SSH_FXP_OPEN
    assert channel.sent[2][4] == SSH_FXP_READ
    assert channel.sent[5][4] == SSH_FXP_CLOSE


def test_sftp_upload_writes_file_and_closes(tmp_path):
    source = tmp_path / "backup.cfg"
    source.write_bytes(b"config")
    channel = FakeSFTPChannel(
        [
            packet(bytes([SSH_FXP_VERSION]) + struct.pack(">I", 3)),
            packet(bytes([SSH_FXP_HANDLE]) + struct.pack(">I", 1) + string(b"H")),
            status(2, SSH_FX_OK),
            status(3, SSH_FX_OK),
        ]
    )
    client = SFTPClient(channel)

    client.upload(source, "/remote/backup.cfg")

    assert channel.sent[1][4] == SSH_FXP_OPEN
    assert channel.sent[2][4] == SSH_FXP_WRITE
    assert b"config" in channel.sent[2]
    assert channel.sent[3][4] == SSH_FXP_CLOSE
