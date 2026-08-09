import socket

from maxconn.transport.ssh import messages
from maxconn.transport.ssh.negotiate import establish_encrypted_session
from maxconn.transport.ssh.wire import Reader, encode_string


def test_establish_encrypted_session_then_service_request_round_trip(ssh_server):
    """The strongest proof the encrypted framing works both ways: after
    NEWKEYS, send an encrypted SSH_MSG_SERVICE_REQUEST and successfully
    decrypt+verify-MAC the server's real encrypted SSH_MSG_SERVICE_ACCEPT."""
    sock = socket.create_connection((ssh_server.host, ssh_server.port), timeout=5.0)
    try:
        session = establish_encrypted_session(sock)
        assert len(session.session_id) == 32
        assert len(session.host_key_blob) > 0

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
