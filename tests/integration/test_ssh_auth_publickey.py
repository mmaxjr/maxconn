import socket

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from maxconn.exceptions import AuthenticationError
from maxconn.transport.ssh.auth import authenticate_publickey, request_userauth_service
from maxconn.transport.ssh.negotiate import establish_encrypted_session


def test_publickey_authentication_succeeds_with_authorized_key(ssh_server):
    sock = socket.create_connection((ssh_server.host, ssh_server.port), timeout=5.0)
    try:
        session = establish_encrypted_session(sock)
        request_userauth_service(session)
        # ssh_server.client_key is a paramiko.RSAKey; `.key` is the
        # underlying `cryptography` RSAPrivateKey it wraps.
        authenticate_publickey(session, ssh_server.username, ssh_server.client_key.key)  # must not raise
    finally:
        sock.close()


def test_publickey_authentication_fails_with_unauthorized_key(ssh_server):
    unauthorized_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    sock = socket.create_connection((ssh_server.host, ssh_server.port), timeout=5.0)
    try:
        session = establish_encrypted_session(sock)
        request_userauth_service(session)
        with pytest.raises(AuthenticationError):
            authenticate_publickey(session, ssh_server.username, unauthorized_key)
    finally:
        sock.close()
