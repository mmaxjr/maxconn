import pytest

from maxconn.exceptions import ProtocolError
from maxconn.transport.ssh import messages
from maxconn.transport.ssh.kex import (
    ENCRYPTION_ALGORITHMS,
    KEX_ALGORITHMS,
    MAC_ALGORITHMS,
    SERVER_HOST_KEY_ALGORITHMS,
    build_kexinit,
    negotiate,
    parse_kexinit,
)


def test_build_kexinit_starts_with_message_type_and_16_byte_cookie():
    cookie = b"\x01" * 16
    payload = build_kexinit(cookie=cookie)
    assert payload[0] == messages.SSH_MSG_KEXINIT
    assert payload[1:17] == cookie


def test_build_kexinit_rejects_wrong_size_cookie():
    with pytest.raises(ValueError):
        build_kexinit(cookie=b"\x00" * 10)


def test_build_then_parse_kexinit_round_trips():
    cookie = b"\xab" * 16
    payload = build_kexinit(cookie=cookie)
    parsed = parse_kexinit(payload)

    assert parsed.cookie == cookie
    assert parsed.kex_algorithms == KEX_ALGORITHMS
    assert parsed.server_host_key_algorithms == SERVER_HOST_KEY_ALGORITHMS
    assert parsed.encryption_algorithms_client_to_server == ENCRYPTION_ALGORITHMS
    assert parsed.encryption_algorithms_server_to_client == ENCRYPTION_ALGORITHMS
    assert parsed.mac_algorithms_client_to_server == MAC_ALGORITHMS
    assert parsed.mac_algorithms_server_to_client == MAC_ALGORITHMS
    assert parsed.first_kex_packet_follows is False


def test_kexinit_offers_legacy_and_ecdh_compatibility_algorithms():
    assert KEX_ALGORITHMS[:3] == [
        "ecdh-sha2-nistp256",
        "diffie-hellman-group14-sha256",
        "diffie-hellman-group14-sha1",
    ]
    assert "ecdsa-sha2-nistp256" in SERVER_HOST_KEY_ALGORITHMS
    assert "ssh-rsa" in SERVER_HOST_KEY_ALGORITHMS
    assert "hmac-sha1" in MAC_ALGORITHMS


def test_parse_kexinit_rejects_wrong_message_type():
    with pytest.raises(ProtocolError):
        parse_kexinit(bytes([99]) + b"\x00" * 16)


def test_negotiate_picks_first_client_preference_server_supports():
    assert negotiate(["a", "b", "c"], ["c", "b"], "test") == "b"


def test_negotiate_raises_when_no_overlap():
    with pytest.raises(ProtocolError):
        negotiate(["a", "b"], ["c", "d"], "test")
