from maxconn.transport.ssh.keys import derive_session_keys


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


def test_derive_session_keys_can_extend_past_one_hash_block():
    keys = derive_session_keys(
        shared_secret=42,
        exchange_hash=b"\x02" * 32,
        session_id=b"\x02" * 32,
        enc_key_length=64,  # bigger than a single SHA-256 output (32 bytes)
    )
    assert len(keys.enc_key_client_to_server) == 64
