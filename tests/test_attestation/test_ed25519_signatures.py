"""
tests/test_attestation/test_ed25519_signatures.py
Unit tests for Ed25519 digital signature signing and verification over canonical manifests.
"""
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from sovereign.attestation.signer import (
    generate_manifest,
    sign_manifest,
    verify_manifest_signature,
)


def test_ed25519_sign_and_verify(temp_dir: Path):
    """Verify generating, signing, and verifying an attestation manifest."""
    # Create sample files
    f1 = temp_dir / "model_weights.bin"
    f1.write_bytes(b"MOCK_WEIGHTS_CONTENT_001")
    f2 = temp_dir / "config.json"
    f2.write_text('{"temperature": 0.7}', encoding="utf-8")

    manifest = generate_manifest(temp_dir, ["model_weights.bin", "config.json"])
    assert len(manifest.entries) == 2
    assert "model_weights.bin" in manifest.entries

    # Load keypair
    priv_path = Path("tests/fixtures/test_ed25519_private.pem")
    pub_path = Path("tests/fixtures/test_ed25519_public.pub")

    priv_pem = priv_path.read_bytes()
    pub_pem = pub_path.read_bytes()

    sig = sign_manifest(manifest, priv_pem)
    assert len(sig) == 128  # 64 bytes hex-encoded

    manifest_dict = manifest.model_dump()
    manifest_dict["signature"] = sig

    # Verify signature
    assert verify_manifest_signature(manifest_dict, pub_pem) is True


def test_tampered_manifest_fails_signature(temp_dir: Path):
    """Verify that altering any entry or metadata invalidates the Ed25519 signature."""
    f1 = temp_dir / "code.py"
    f1.write_text("print('hello')", encoding="utf-8")

    manifest = generate_manifest(temp_dir, ["code.py"])
    priv_pem = Path("tests/fixtures/test_ed25519_private.pem").read_bytes()
    pub_pem = Path("tests/fixtures/test_ed25519_public.pub").read_bytes()

    sig = sign_manifest(manifest, priv_pem)
    manifest_dict = manifest.model_dump()
    manifest_dict["signature"] = sig

    # 1. Tamper with entry SHA-256
    tampered_1 = dict(manifest_dict)
    tampered_1["entries"]["code.py"]["sha256"] = "0" * 64
    assert verify_manifest_signature(tampered_1, pub_pem) is False

    # 2. Tamper with generated_iso
    tampered_2 = dict(manifest_dict)
    tampered_2["generated_iso"] = "2020-01-01T00:00:00Z"
    assert verify_manifest_signature(tampered_2, pub_pem) is False

    # 3. Wrong public key fails
    other_priv = ed25519.Ed25519PrivateKey.generate()
    other_pub_pem = other_priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    assert verify_manifest_signature(manifest_dict, other_pub_pem) is False
