import socket

from maxconn.transport.ssh import messages
from maxconn.transport.ssh.auth import authenticate_password, request_userauth_service
from maxconn.transport.ssh.channel import SSHChannel, open_session_channel
from maxconn.transport.ssh.negotiate import establish_encrypted_session
from maxconn.transport.ssh.wire import Reader, encode_string, encode_uint32


class _QueuedSession:
    def __init__(self, payloads):
        self._payloads = list(payloads)

    def recv_message(self):
        return self._payloads.pop(0)


def _authenticated_session(ssh_server):
    sock = socket.create_connection((ssh_server.host, ssh_server.port), timeout=5.0)
    session = establish_encrypted_session(sock)
    request_userauth_service(session)
    authenticate_password(session, ssh_server.username, ssh_server.password)
    return sock, session


def test_exec_command_returns_output_and_closes(ssh_server):
    sock, session = _authenticated_session(ssh_server)
    try:
        channel = open_session_channel(session)
        channel.request_exec("show version")

        collected = b""
        for _ in range(20):
            collected += channel.recv_data()
            if channel.closed:
                break

        assert b"echo:show version" in collected
        assert channel.closed
    finally:
        sock.close()


def test_shell_session_echoes_commands(ssh_server):
    sock, session = _authenticated_session(ssh_server)
    try:
        channel = open_session_channel(session)
        channel.request_shell()

        banner = b""
        while b"device>" not in banner:
            banner += channel.recv_data()
        assert b"Welcome" in banner

        channel.send_data(b"show status\n")
        reply = b""
        while b"device>" not in reply:
            reply += channel.recv_data()
        assert b"echo:show status" in reply

        channel.send_data(b"exit\n")
        while not channel.closed:
            channel.recv_data()
    finally:
        sock.close()


def test_recv_data_skips_control_messages_until_channel_data_arrives():
    control_payload = bytes([messages.SSH_MSG_CHANNEL_WINDOW_ADJUST]) + encode_uint32(0) + encode_uint32(1024)
    data_payload = bytes([messages.SSH_MSG_CHANNEL_DATA]) + encode_uint32(0) + encode_string(b"ready>")
    channel = SSHChannel(_QueuedSession([control_payload, data_payload]), local_id=0, peer_id=1)

    assert channel.recv_data() == b"ready>"


def test_request_subsystem_sends_sftp_channel_request():
    class Session:
        def __init__(self):
            self.sent = []

        def send_message(self, payload):
            self.sent.append(payload)

    session = Session()
    channel = SSHChannel(session, local_id=0, peer_id=7)

    channel.request_subsystem("sftp")

    reader = Reader(session.sent[0])
    assert reader.read_byte() == messages.SSH_MSG_CHANNEL_REQUEST
    assert reader.read_uint32() == 7
    assert reader.read_string() == b"subsystem"
    assert reader.read_byte() == 0
    assert reader.read_string() == b"sftp"
