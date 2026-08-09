import socket

import pytest

from maxconn.exceptions import AuthenticationError
from maxconn.transport.ssh.auth import authenticate_password, request_userauth_service
from maxconn.transport.ssh.negotiate import establish_encrypted_session


def test_password_authentication_succeeds_with_correct_credentials(ssh_server):
    sock = socket.create_connection((ssh_server.host, ssh_server.port), timeout=5.0)
    try:
        session = establish_encrypted_session(sock)
        request_userauth_service(session)
        authenticate_password(session, ssh_server.username, ssh_server.password)  # must not raise
    finally:
        sock.close()


def test_password_authentication_fails_with_wrong_password(ssh_server):
    sock = socket.create_connection((ssh_server.host, ssh_server.port), timeout=5.0)
    try:
        session = establish_encrypted_session(sock)
        request_userauth_service(session)
        with pytest.raises(AuthenticationError):
            authenticate_password(session, ssh_server.username, "wrong-password")
    finally:
        sock.close()
