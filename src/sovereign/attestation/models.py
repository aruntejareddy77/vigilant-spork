"""
src/sovereign/attestation/models.py
Pydantic schemas for the Startup Attestation & Cryptographic Manifest Subsystem.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ManifestEntry(BaseModel):
    """Represents a verified catalog entry for a model weight, binary, or script."""
    model_config = ConfigDict(extra="forbid")

    path: str = Field(description="Normalized relative path to asset")
    size_bytes: int = Field(ge=0, description="Exact file size in bytes")
    sha256: str = Field(min_length=64, max_length=64, description="Full file SHA-256 hex digest")
    chunk_first_64mb_sha256: str = Field(min_length=64, max_length=64, description="SHA-256 of first 64MB chunk")
    chunk_last_64mb_sha256: str = Field(min_length=64, max_length=64, description="SHA-256 of last 64MB chunk")
    mtime_iso: str = Field(description="Last modified timestamp in ISO 8601 format")
    inode: str = Field(default="0", description="Filesystem inode as string (avoids RFC 8785 safe-integer overflow on Windows)")


class AttestationManifest(BaseModel):
    """Cryptographically signed catalog of all executable assets and model files."""
    model_config = ConfigDict(extra="forbid")

    manifest_version: str = Field(default="1.0.0", description="Manifest schema version")
    generated_iso: str = Field(description="ISO 8601 timestamp when manifest was produced")
    entries: Dict[str, ManifestEntry] = Field(default_factory=dict, description="Map of relative path to entry")
    signature: Optional[str] = Field(default=None, description="Hex-encoded Ed25519 signature over canonical manifest")


class AttestationResult(BaseModel):
    """Diagnostic outcome of an attestation verification run."""
    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    mode: str = Field(description="'full' byte-by-byte or 'sparse' warm restart check")
    files_checked: int
    discrepancies: List[str] = Field(default_factory=list)
    duration_ms: float
