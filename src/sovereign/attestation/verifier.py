"""
src/sovereign/attestation/verifier.py
Two-tier startup attestation guard enforcing cryptographic supply chain integrity.
"""
import json
import logging
from pathlib import Path
import time
from typing import List, Optional, Union

from sovereign.attestation.hasher import hash_full_file, hash_sparse_chunks
from sovereign.attestation.models import AttestationManifest, AttestationResult
from sovereign.attestation.signer import verify_manifest_signature
from sovereign.audit.ledger import AuditLedger

logger = logging.getLogger("sovereign.attestation.verifier")


class AttestationError(Exception):
    """Raised when startup attestation fails closed on corrupted or missing assets."""
    pass


class AttestationGuard:
    """
    Enforces cryptographic integrity on startup.
    Executes full byte-by-byte SHA-256 verification on cold boot / --full-attest,
    and fast (<2s) 64MB sparse head/tail chunk checks on warm restarts.
    Fails closed by default unless --dev-mode or --mock-models is passed.
    """

    def __init__(self, public_key_pem_or_path: Union[str, Path, bytes]):
        if isinstance(public_key_pem_or_path, (str, Path)) and Path(public_key_pem_or_path).exists():
            with open(public_key_pem_or_path, "rb") as f:
                self.public_key_pem = f.read()
        elif isinstance(public_key_pem_or_path, str):
            self.public_key_pem = public_key_pem_or_path.encode("utf-8")
        else:
            self.public_key_pem = public_key_pem_or_path

    def verify_manifest(
        self,
        manifest_path: Union[str, Path],
        root_dir: Optional[Union[str, Path]] = None,
        full_attest: bool = False,
        dev_mode: bool = False,
        mock_models: bool = False,
        audit_ledger: Optional[AuditLedger] = None,
    ) -> AttestationResult:
        """
        Validates the Ed25519 signature of the manifest and evaluates file integrity.
        """
        start_time = time.perf_counter()
        m_path = Path(manifest_path).resolve()
        if not m_path.exists():
            err_msg = f"Attestation manifest not found: {m_path}"
            if not (dev_mode or mock_models):
                raise AttestationError(err_msg)
            return AttestationResult(
                is_valid=False,
                mode="missing_manifest",
                files_checked=0,
                discrepancies=[err_msg],
                duration_ms=0.0,
            )

        with open(m_path, "r", encoding="utf-8") as f:
            manifest_dict = json.load(f)

        # 1. Verify Ed25519 Digital Signature
        sig_valid = verify_manifest_signature(manifest_dict, self.public_key_pem)
        if not sig_valid:
            err_msg = "Attestation manifest digital signature is INVALID or TAMPERED."
            if not (dev_mode or mock_models):
                raise AttestationError(err_msg)
            return AttestationResult(
                is_valid=False,
                mode="invalid_signature",
                files_checked=0,
                discrepancies=[err_msg],
                duration_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )

        manifest = AttestationManifest(**manifest_dict)
        base_dir = Path(root_dir).resolve() if root_dir else m_path.parent
        discrepancies: List[str] = []
        files_checked = 0
        mode = "full" if full_attest else "sparse"

        # 2. Check each cataloged file entry
        for rel_path, entry in manifest.entries.items():
            files_checked += 1
            full_path = base_dir / rel_path

            if not full_path.exists():
                discrepancies.append(f"Missing file: {rel_path}")
                continue

            stat = full_path.stat()
            if stat.st_size != entry.size_bytes:
                discrepancies.append(
                    f"Size mismatch for {rel_path}: actual {stat.st_size} bytes != expected {entry.size_bytes} bytes"
                )
                continue

            if full_attest:
                actual_sha = hash_full_file(full_path)
                if actual_sha != entry.sha256:
                    discrepancies.append(
                        f"Full SHA-256 mismatch for {rel_path}: computed {actual_sha} != expected {entry.sha256}"
                    )
            else:
                # Fast warm check (<2s): 64MB head and tail chunks
                first_64, last_64, _ = hash_sparse_chunks(full_path)
                if first_64 != entry.chunk_first_64mb_sha256:
                    discrepancies.append(f"Sparse first-64MB chunk mismatch for {rel_path}")
                elif last_64 != entry.chunk_last_64mb_sha256:
                    discrepancies.append(f"Sparse last-64MB chunk mismatch for {rel_path}")

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if discrepancies:
            if dev_mode or mock_models:
                # Log audit warning and allow non-fatal return
                if audit_ledger:
                    try:
                        audit_ledger.append_event(
                            session_id="system-startup",
                            event_type="ATTESTATION_WARNING_BYPASS",
                            actor_role="attestation-guard",
                            payload={
                                "dev_mode": dev_mode,
                                "mock_models": mock_models,
                                "discrepancies": discrepancies,
                                "duration_ms": duration_ms,
                            },
                        )
                    except Exception as exc:
                        logger.error(f"Failed to log attestation bypass to audit ledger: {exc}")
                return AttestationResult(
                    is_valid=False,
                    mode=mode,
                    files_checked=files_checked,
                    discrepancies=discrepancies,
                    duration_ms=duration_ms,
                )
            else:
                # Strict fail-closed in production
                raise AttestationError(
                    f"Startup attestation failed with {len(discrepancies)} discrepancies:\n"
                    + "\n".join(f" - {d}" for d in discrepancies)
                )

        return AttestationResult(
            is_valid=True,
            mode=mode,
            files_checked=files_checked,
            discrepancies=[],
            duration_ms=duration_ms,
        )
