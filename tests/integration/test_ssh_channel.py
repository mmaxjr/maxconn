import socket

from maxconn.transport.ssh.auth import authenticate_password, request_userauth_service
from maxconn.transport.ssh.channel import open_session_channel
from maxconn.transport.ssh.negotiate import establish_encrypted_session


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
