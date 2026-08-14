import hashlib

from maxconn.transport.ssh.keys import derive_session_keys
from maxconn.transport.ssh.wire import encode_mpint


def test_derive_session_keys_lengths():
    keys = derive_session_keys(shared_secret=12345, exchange_hash=b"\x01" * 32, session_id=b"\x01" * 32)
    assert len(keys.iv_client_to_server) == 16
    assert len(keys.iv_server_to_client) == 16
    assert len(keys.enc_key_client_to_server) == 16
    assert len(keys.enc_key_server_to_client) == 16
    assert len(keys.mac_key_client_to_server) == 32
    assert len(keys.mac_key_server_to_client) == 32


def test_derive_session_keys_are_all_distinct():
    keys = derive_session_keys(shared_secret=12345, exchange_hash=b"\x01" * 32, session_id=b"\x01" * 32)
    values = [
        keys.iv_client_to_server,
        keys.iv_server_to_client,
        keys.enc_key_client_to_server,
        keys.enc_key_server_to_client,
        keys.mac_key_client_to_server,
        keys.mac_key_server_to_client,
    ]
    assert len(set(values)) == len(values)


def test_derive_session_keys_is_deterministic():
    a = derive_session_keys(shared_secret=999, exchange_hash=b"\xff" * 32, session_id=b"\xff" * 32)
    b = derive_session_keys(shared_secret=999, exchange_hash=b"\xff" * 32, session_id=b"\xff" * 32)
    assert a == b


def test_derive_session_keys_changes_with_shared_secret():
    a = derive_session_keys(shared_secret=1, exchange_hash=b"\xaa" * 32, session_id=b"\xaa" * 32)
    b = derive_session_keys(shared_secret=2, exchange_hash=b"\xaa" * 32, session_id=b"\xaa" * 32)
    assert a != b


def test_derive_session_keys_uses_the_given_hash_algorithm():
    # RFC 4253 §7.2: session keys MUST be derived with the same HASH used
    # for the exchange hash H. When diffie-hellman-group14-sha1 is
    # negotiated, H is SHA-1, so key derivation must also use SHA-1 -
    # otherwise a spec-compliant server computes different keys and every
    # encrypted packet fails MAC verification.
    sha256_keys = derive_session_keys(
        shared_secret=42, exchange_hash=b"\xaa" * 20, session_id=b"\xaa" * 20, hash_name="sha256"
    )
    sha1_keys = derive_session_keys(
        shared_secret=42, exchange_hash=b"\xaa" * 20, session_id=b"\xaa" * 20, hash_name="sha1"
    )
    assert sha256_keys != sha1_keys

    # Cross-check against hashlib directly using the same mpint encoding the
    # implementation uses, so this test fails if the hash silently reverts
    # to sha256 instead of honoring hash_name.
    expected = hashlib.sha1(encode_mpint(42) + b"\xaa" * 20 + b"A" + b"\xaa" * 20).digest()[:16]
    assert sha1_keys.iv_client_to_server == expected


def test_derive_session_keys_supports_different_mac_key_lengths_per_direction():
    # RFC 4253 §7.1 allows a different MAC algorithm (and therefore key
    # length) per direction - e.g. hmac-sha1 (20 bytes) one way and
    # hmac-sha2-256 (32 bytes) the other.
    keys = derive_session_keys(
        shared_secret=7,
        exchange_hash=b"\x03" * 32,
        session_id=b"\x03" * 32,
        mac_key_length_client_to_server=20,
        mac_key_length_server_to_client=32,
    )
    assert len(keys.mac_key_client_to_server) == 20
    assert len(keys.mac_key_server_to_client) == 32
    # The shorter key must be a true prefix of what a 32-byte request would
    # produce (same underlying hash chain, just truncated differently) -
    # not derived from separate/inconsistent state.
    long_keys = derive_session_keys(
        shared_secret=7,
        exchange_hash=b"\x03" * 32,
        session_id=b"\x03" * 32,
        mac_key_length_client_to_server=32,
        mac_key_length_server_to_client=32,
    )
    assert long_keys.mac_key_client_to_server[:20] == keys.mac_key_client_to_server


def test_derive_session_keys_can_extend_past_one_hash_block():
    keys = derive_session_keys(
        shared_secret=42,
        exchange_hash=b"\x02" * 32,
        session_id=b"\x02" * 32,
        enc_key_length=64,  # bigger than a single SHA-256 output (32 bytes)
    )
    assert len(keys.enc_key_client_to_server) == 64
