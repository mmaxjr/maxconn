import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from maxconn.exceptions import ProtocolError
from maxconn.transport.ssh.hostkey import parse_rsa_host_key, verify_host_key_signature
from maxconn.transport.ssh.wire import encode_mpint, encode_string


def _build_host_key_blob(public_key: rsa.RSAPublicKey) -> bytes:
    numbers = public_key.public_numbers()
    return encode_string(b"ssh-rsa") + encode_mpint(numbers.e) + encode_mpint(numbers.n)


def _build_signature_blob(private_key: rsa.RSAPrivateKey, algorithm: str, message: bytes) -> bytes:
    hash_cls = {"ssh-rsa": hashes.SHA1, "rsa-sha2-256": hashes.SHA256}[algorithm]
    signature = private_key.sign(message, padding.PKCS1v15(), hash_cls())
    return encode_string(algorithm.encode("ascii")) + encode_string(signature)


@pytest.fixture(scope="module")
def keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def test_parse_rsa_host_key_recovers_public_numbers(keypair):
    _private_key, public_key = keypair
    blob = _build_host_key_blob(public_key)
    parsed = parse_rsa_host_key(blob)
    assert parsed.public_numbers() == public_key.public_numbers()


def test_parse_rsa_host_key_rejects_unsupported_type():
    blob = encode_string(b"ssh-ed25519") + encode_string(b"whatever")
    with pytest.raises(ProtocolError):
        parse_rsa_host_key(blob)


def test_verify_host_key_signature_succeeds_for_rsa_sha2_256(keypair):
    private_key, public_key = keypair
    host_key_blob = _build_host_key_blob(public_key)
    exchange_hash = b"\x11" * 32
    signature_blob = _build_signature_blob(private_key, "rsa-sha2-256", exchange_hash)

    verify_host_key_signature(host_key_blob, signature_blob, exchange_hash)  # must not raise


def test_verify_host_key_signature_succeeds_for_legacy_ssh_rsa(keypair):
    private_key, public_key = keypair
    host_key_blob = _build_host_key_blob(public_key)
    exchange_hash = b"\x22" * 32
    signature_blob = _build_signature_blob(private_key, "ssh-rsa", exchange_hash)

    verify_host_key_signature(host_key_blob, signature_blob, exchange_hash)  # must not raise


def test_verify_host_key_signature_rejects_tampered_hash(keypair):
    private_key, public_key = keypair
    host_key_blob = _build_host_key_blob(public_key)
    exchange_hash = b"\x33" * 32
    signature_blob = _build_signature_blob(private_key, "rsa-sha2-256", exchange_hash)

    with pytest.raises(ProtocolError):
        verify_host_key_signature(host_key_blob, signature_blob, b"\x44" * 32)


def test_verify_host_key_signature_rejects_wrong_key(keypair):
    _private_key, public_key = keypair
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    host_key_blob = _build_host_key_blob(public_key)  # blob claims the fixture's key...
    exchange_hash = b"\x55" * 32
    # ...but the signature was made by a totally different key.
    signature_blob = _build_signature_blob(other_private_key, "rsa-sha2-256", exchange_hash)

    with pytest.raises(ProtocolError):
        verify_host_key_signature(host_key_blob, signature_blob, exchange_hash)


def test_verify_host_key_signature_rejects_unknown_algorithm(keypair):
    _private_key, public_key = keypair
    host_key_blob = _build_host_key_blob(public_key)
    exchange_hash = b"\x66" * 32
    signature_blob = encode_string(b"rsa-sha2-999") + encode_string(b"not-a-real-signature")

    with pytest.raises(ProtocolError):
        verify_host_key_signature(host_key_blob, signature_blob, exchange_hash)
