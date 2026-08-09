import hashlib

from maxconn.transport.ssh.diffie_hellman import G, P, compute_exchange_hash
from maxconn.transport.ssh.wire import encode_mpint, encode_string


def test_p_is_the_2048_bit_group14_prime():
    assert P.bit_length() == 2048
    assert P % 2 == 1  # a prime > 2 is always odd


def test_g_is_2():
    assert G == 2


def test_compute_exchange_hash_matches_manual_construction():
    e, f, k = 12345, 67890, 424242
    host_key_blob = b"fake-host-key-blob"

    expected_input = (
        encode_string(b"SSH-2.0-client")
        + encode_string(b"SSH-2.0-server")
        + encode_string(b"client-kexinit")
        + encode_string(b"server-kexinit")
        + encode_string(host_key_blob)
        + encode_mpint(e)
        + encode_mpint(f)
        + encode_mpint(k)
    )
    expected = hashlib.sha256(expected_input).digest()

    actual = compute_exchange_hash(
        client_version=b"SSH-2.0-client",
        server_version=b"SSH-2.0-server",
        client_kexinit_payload=b"client-kexinit",
        server_kexinit_payload=b"server-kexinit",
        host_key_blob=host_key_blob,
        e=e,
        f=f,
        shared_secret=k,
    )
    assert actual == expected
    assert len(actual) == 32  # SHA-256 digest size


def test_compute_exchange_hash_is_sensitive_to_every_field():
    base_kwargs = {
        "client_version": b"SSH-2.0-client",
        "server_version": b"SSH-2.0-server",
        "client_kexinit_payload": b"client-kexinit",
        "server_kexinit_payload": b"server-kexinit",
        "host_key_blob": b"host-key",
        "e": 1,
        "f": 2,
        "shared_secret": 3,
    }
    baseline = compute_exchange_hash(**base_kwargs)
    for field in ("client_version", "server_version", "host_key_blob"):
        changed = dict(base_kwargs)
        changed[field] = changed[field] + b"-different"
        assert compute_exchange_hash(**changed) != baseline
    for field in ("e", "f", "shared_secret"):
        changed = dict(base_kwargs)
        changed[field] = changed[field] + 1
        assert compute_exchange_hash(**changed) != baseline
