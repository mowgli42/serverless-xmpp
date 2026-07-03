"""TLS certificate generation and fingerprint verification for direct P2P."""

from __future__ import annotations

import datetime
import ipaddress
import logging
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

logger = logging.getLogger(__name__)


def cert_fingerprint(cert_data: bytes | None, *, der: bool = False) -> str:
    if not cert_data:
        raise ValueError("No certificate data")
    if der:
        cert = x509.load_der_x509_certificate(cert_data)
    else:
        cert = x509.load_pem_x509_certificate(cert_data)
    digest = cert.fingerprint(hashes.SHA256())
    return "SHA256:" + digest.hex().upper()


def normalize_fingerprint(value: str) -> str:
    cleaned = value.strip().upper().replace(" ", "")
    if cleaned.startswith("SHA256:"):
        return cleaned
    return "SHA256:" + cleaned.removeprefix("SHA256:")


def verify_fingerprint(cert_data: bytes | None, expected: str | None, *, der: bool = False) -> bool:
    if not expected:
        return True
    if not cert_data:
        return False
    return cert_fingerprint(cert_data, der=der) == normalize_fingerprint(expected)


def ensure_p2p_certificates(
    cert_dir: Path,
    common_name: str = "xmpp-p2p-local",
) -> tuple[Path, Path, str]:
    """Create or load self-signed TLS cert/key for direct P2P. Returns paths + fingerprint."""
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / "p2p-cert.pem"
    key_path = cert_dir / "p2p-key.pem"

    if cert_path.exists() and key_path.exists():
        cert_pem = cert_path.read_bytes()
        return cert_path, key_path, cert_fingerprint(cert_pem)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.DNSName("*.local"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    fp = cert_fingerprint(cert_path.read_bytes())
    logger.info("Generated P2P TLS certificate (fingerprint %s)", fp)
    return cert_path, key_path, fp
