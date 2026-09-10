"""
src/sovereign/attestation/__init__.py
Startup Attestation Subsystem exports.
"""
from sovereign.attestation.hasher import CHUNK_64MB, hash_full_file, hash_sparse_chunks
from sovereign.attestation.models import AttestationManifest, AttestationResult, ManifestEntry
from sovereign.attestation.signer import generate_manifest, sign_manifest, verify_manifest_signature
from sovereign.attestation.verifier import AttestationError, AttestationGuard

__all__ = [
    "CHUNK_64MB",
    "hash_full_file",
    "hash_sparse_chunks",
    "ManifestEntry",
    "AttestationManifest",
    "AttestationResult",
    "generate_manifest",
    "sign_manifest",
    "verify_manifest_signature",
    "AttestationError",
    "AttestationGuard",
]
