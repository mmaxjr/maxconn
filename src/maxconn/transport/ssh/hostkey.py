"""RSA host key parsing and signature verification (RFC 4253 section 6.6,
RFC 8332 for the SHA-2 signature variants)."""

from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa, utils

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


def parse_ecdsa_nistp256_host_key(blob: bytes) -> ec.EllipticCurvePublicKey:
    reader = Reader(blob)
    key_type = reader.read_string().decode("ascii")
    if key_type != "ecdsa-sha2-nistp256":
        raise ProtocolError(f"Unsupported ECDSA host key type: {key_type!r}")
    curve_name = reader.read_string().decode("ascii")
    if curve_name != "nistp256":
        raise ProtocolError(f"Unsupported ECDSA curve: {curve_name!r}")
    point = reader.read_string()
    return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)


def verify_host_key_signature(host_key_blob: bytes, signature_blob: bytes, exchange_hash: bytes) -> None:
    """Raises ProtocolError if the signature does not validate against `exchange_hash`."""
    key_reader = Reader(host_key_blob)
    host_key_type = key_reader.read_string().decode("ascii")

    reader = Reader(signature_blob)
    sig_algorithm = reader.read_string().decode("ascii")
    signature = reader.read_string()

    try:
        if host_key_type == "ssh-rsa":
            public_key = parse_rsa_host_key(host_key_blob)
            hash_cls = _SIGNATURE_HASH_ALGORITHMS.get(sig_algorithm)
            if hash_cls is None:
                raise ProtocolError(f"Unsupported host key signature algorithm: {sig_algorithm!r}")
            public_key.verify(signature, exchange_hash, padding.PKCS1v15(), hash_cls())
            return

        if host_key_type == "ecdsa-sha2-nistp256":
            if sig_algorithm != "ecdsa-sha2-nistp256":
                raise ProtocolError(f"Unsupported ECDSA signature algorithm: {sig_algorithm!r}")
            public_key = parse_ecdsa_nistp256_host_key(host_key_blob)
            sig_reader = Reader(signature)
            r = int.from_bytes(sig_reader.read_string(), "big")
            s = int.from_bytes(sig_reader.read_string(), "big")
            der_signature = utils.encode_dss_signature(r, s)
            public_key.verify(der_signature, exchange_hash, ec.ECDSA(hashes.SHA256()))
            return

        raise ProtocolError(f"Unsupported host key type: {host_key_type!r}")
    except InvalidSignature as exc:
        raise ProtocolError("SSH host key signature verification failed") from exc
