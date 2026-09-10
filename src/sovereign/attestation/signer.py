"""
src/sovereign/attestation/signer.py
Ed25519 digital signature signing and verification for attestation manifests.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Union
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
import rfc8785

from sovereign.attestation.hasher import hash_full_file, hash_sparse_chunks
from sovereign.attestation.models import AttestationManifest, ManifestEntry


def generate_manifest(
    root_dir: Union[str, Path],
    relative_file_paths: List[str],
) -> AttestationManifest:
    """
    Scans specified files relative to root_dir and computes full and sparse hashes,
    sizes, and stat metadata to construct an unsigned AttestationManifest.
    """
    root = Path(root_dir).resolve()
    entries: Dict[str, ManifestEntry] = {}

    for rel_path in relative_file_paths:
        norm_rel = Path(rel_path).as_posix()
        full_path = root / rel_path
        if not full_path.exists():
            continue

        stat_info = full_path.stat()
        full_sha256 = hash_full_file(full_path)
        first_64, last_64, size_bytes = hash_sparse_chunks(full_path)

        mtime_iso = datetime.fromtimestamp(stat_info.st_mtime, timezone.utc).isoformat()

        entries[norm_rel] = ManifestEntry(
            path=norm_rel,
            size_bytes=size_bytes,
            sha256=full_sha256,
            chunk_first_64mb_sha256=first_64,
            chunk_last_64mb_sha256=last_64,
            mtime_iso=mtime_iso,
            inode=str(getattr(stat_info, "st_ino", 0)),
        )

    return AttestationManifest(
        manifest_version="1.0.0",
        generated_iso=datetime.now(timezone.utc).isoformat(),
        entries=entries,
        signature=None,
    )


def sign_manifest(
    manifest_data: Union[AttestationManifest, Dict[str, Any]],
    private_key_pem: Union[str, bytes],
) -> str:
    """
    Signs the RFC 8785 canonical bytes of an AttestationManifest (excluding signature field)
    using an Ed25519 private key. Returns the hex-encoded signature.
    """
    if isinstance(manifest_data, AttestationManifest):
        raw_dict = manifest_data.model_dump()
    else:
        raw_dict = dict(manifest_data)

    # Exclude signature from the signing payload
    raw_dict.pop("signature", None)

    # Load private key
    key_bytes = private_key_pem.encode("utf-8") if isinstance(private_key_pem, str) else private_key_pem
    priv_key = serialization.load_pem_private_key(key_bytes, password=None)
    if not isinstance(priv_key, ed25519.Ed25519PrivateKey):
        raise ValueError("Provided key is not a valid Ed25519 private key.")

    # Canonicalize and sign
    canonical_bytes = rfc8785.dumps(raw_dict)
    sig_bytes = priv_key.sign(canonical_bytes)
    return sig_bytes.hex()


def verify_manifest_signature(
    manifest_data: Union[AttestationManifest, Dict[str, Any]],
    public_key_pem: Union[str, bytes],
) -> bool:
    """
    Verifies the Ed25519 digital signature over the RFC 8785 canonical bytes of the manifest.
    Returns True if valid, False otherwise.
    """
    if isinstance(manifest_data, AttestationManifest):
        raw_dict = manifest_data.model_dump()
    else:
        raw_dict = dict(manifest_data)

    claimed_sig_hex = raw_dict.pop("signature", None)
    if not claimed_sig_hex:
        return False

    try:
        sig_bytes = bytes.fromhex(claimed_sig_hex)
    except ValueError:
        return False

    key_bytes = public_key_pem.encode("utf-8") if isinstance(public_key_pem, str) else public_key_pem
    try:
        pub_key = serialization.load_pem_public_key(key_bytes)
        if not isinstance(pub_key, ed25519.Ed25519PublicKey):
            return False

        canonical_bytes = rfc8785.dumps(raw_dict)
        pub_key.verify(sig_bytes, canonical_bytes)
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False
