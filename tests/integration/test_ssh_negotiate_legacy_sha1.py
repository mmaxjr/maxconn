"""End-to-end regression test for the diffie-hellman-group14-sha1 /
hmac-sha1 compatibility fallback (added in v0.1.14 for a real legacy
OpenSSH_6.2 server). This is the scenario that was silently broken by the
session-key-derivation and MAC-direction bugs fixed alongside this test:
without those fixes, the handshake completes but the very first encrypted
packet fails MAC verification.
"""

import socket

from maxconn.transport.ssh import messages
from maxconn.transport.ssh.negotiate import establish_encrypted_session
from maxconn.transport.ssh.wire import Reader, encode_string
from tests.integration.legacy_ssh_server import start_legacy_ssh_server


def test_establish_encrypted_session_over_group14_sha1_fallback():
    server = start_legacy_ssh_server()
    try:
        sock = socket.create_connection((server.host, server.port), timeout=5.0)
        try:
            session = establish_encrypted_session(sock)

            request = bytes([messages.SSH_MSG_SERVICE_REQUEST]) + encode_string(b"ssh-userauth")
            session.send_message(request)

            response = session.recv_message()
            reader = Reader(response)
            msg_type = reader.read_byte()
            service_name = reader.read_string()

            assert msg_type == messages.SSH_MSG_SERVICE_ACCEPT
            assert service_name == b"ssh-userauth"
        finally:
            sock.close()
    finally:
        server.stop()
