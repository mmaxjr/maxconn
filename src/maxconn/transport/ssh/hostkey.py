"""RSA host key parsing and signature verification (RFC 4253 section 6.6,
RFC 8332 for the SHA-2 signature variants)."""

from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from maxconn.exceptions import ProtocolError
from maxconn.transport.ssh.wire import Reader

_SIGNATURE_HASH_ALGORITHMS: dict[str, type[hashes.HashAlgorithm]] = {
    "ssh-rsa": hashes.SHA1,
    "rsa-sha2-256": hashes.SHA256,
    "rsa-sha2-512": hashes.SHA512,
}


def parse_rsa_host_key(blob: bytes) -> rsa.RSAPublicKey:
    reader = Reader(blob)
    key_type = reader.read_string().decode("ascii")
    if key_type != "ssh-rsa":
        raise ProtocolError(f"Unsupported host key type: {key_type!r} (only ssh-rsa is supported in v0.1)")
    e = reader.read_mpint()
    n = reader.read_mpint()
    return rsa.RSAPublicNumbers(e, n).public_key()


def verify_host_key_signature(host_key_blob: bytes, signature_blob: bytes, exchange_hash: bytes) -> None:
    """Raises ProtocolError if the signature does not validate against `exchange_hash`."""
    public_key = parse_rsa_host_key(host_key_blob)

    reader = Reader(signature_blob)
    sig_algorithm = reader.read_string().decode("ascii")
    signature = reader.read_string()

    hash_cls = _SIGNATURE_HASH_ALGORITHMS.get(sig_algorithm)
    if hash_cls is None:
        raise ProtocolError(f"Unsupported host key signature algorithm: {sig_algorithm!r}")

    try:
        public_key.verify(signature, exchange_hash, padding.PKCS1v15(), hash_cls())
    except InvalidSignature as exc:
        raise ProtocolError("SSH host key signature verification failed") from exc
