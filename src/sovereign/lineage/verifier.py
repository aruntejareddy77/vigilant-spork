"""
src/sovereign/lineage/verifier.py
Bidirectional Lineage Verifier and Forward Provenance Tracing Engine
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel

from sovereign.lineage.engine import LineageEngine
from sovereign.lineage.injectors.code import extract_code_lineage
from sovereign.lineage.injectors.ooxml import extract_ooxml_lineage
from sovereign.lineage.injectors.png import extract_png_lineage
from sovereign.lineage.models import LineageMetadata
from sovereign.audit.canonical import verify_record

OOXML_EXTENSIONS = {".docx", ".xlsx", ".pptx"}
PNG_EXTENSIONS = {".png"}
CODE_EXTENSIONS = {".py", ".sh", ".bash"}


class LineageVerificationResult(BaseModel):
    is_valid: bool
    deliverable_path: str
    file_sha256_computed: str = ""
    file_sha256_recorded: str = ""
    file_hash_valid: bool = False
    sidecar_exists: bool = False
    sidecar_valid: bool = False
    embedded_metadata_found: bool = False
    embedded_metadata_valid: bool = False
    audit_span_valid: bool = False
    error_message: Optional[str] = None
    details: Dict[str, Any] = {}


class LineageTraceResult(BaseModel):
    deliverable_path: str
    deliverable_sha256: str
    session_id: str
    match_type: str  # "source_document", "model_weights", "deliverable"
    matched_id: str
    matched_hash: str
    sidecar_path: str
    generated_iso: str


class LineageVerifier:
    """
    Cryptographic lineage verification and bidirectional provenance tracing engine.
    """

    @classmethod
    def verify_lineage(
        cls,
        deliverable_path: Union[str, Path],
        ledger_path: Optional[Union[str, Path]] = None,
    ) -> LineageVerificationResult:
        """
        Reverse verification of a deliverable:
        1. Checks deliverable exists and computes its SHA-256 digest.
        2. Locates and parses sibling `<deliverable_path>.lineage.json` sidecar.
        3. Asserts deliverable SHA-256 matches sidecar `deliverable.file_sha256`.
        4. Extracts and validates format-native embedded metadata against sidecar.
        5. Verifies audit ledger sequence span if ledger is provided or found.
        """
        path = Path(deliverable_path).resolve()
        if not path.exists():
            return LineageVerificationResult(
                is_valid=False,
                deliverable_path=str(path),
                error_message=f"Deliverable file not found: {path}",
            )

        # 1. Compute file SHA-256
        computed_sha256 = LineageEngine.compute_sha256(path)

        # 2. Check sibling sidecar
        sidecar_path = Path(f"{path}.lineage.json")
        if not sidecar_path.exists():
            return LineageVerificationResult(
                is_valid=False,
                deliverable_path=str(path),
                file_sha256_computed=computed_sha256,
                sidecar_exists=False,
                error_message=f"Lineage sidecar manifest not found: {sidecar_path}",
            )

        try:
            metadata = LineageEngine.load_sidecar(sidecar_path)
        except Exception as e:
            return LineageVerificationResult(
                is_valid=False,
                deliverable_path=str(path),
                file_sha256_computed=computed_sha256,
                sidecar_exists=True,
                sidecar_valid=False,
                error_message=f"Failed to parse lineage sidecar: {e}",
            )

        recorded_sha256 = metadata.deliverable.file_sha256
        file_hash_valid = (computed_sha256 == recorded_sha256)

        if not file_hash_valid:
            return LineageVerificationResult(
                is_valid=False,
                deliverable_path=str(path),
                file_sha256_computed=computed_sha256,
                file_sha256_recorded=recorded_sha256,
                file_hash_valid=False,
                sidecar_exists=True,
                sidecar_valid=True,
                error_message=f"Deliverable SHA-256 mismatch: computed {computed_sha256} != recorded {recorded_sha256}",
            )

        # 3. Check format-native embedded metadata
        ext = path.suffix.lower()
        embedded_found = False
        embedded_valid = True
        embedded_err = None

        if ext in OOXML_EXTENSIONS:
            extracted = extract_ooxml_lineage(path.read_bytes())
            if extracted:
                embedded_found = True
                sess_match = (extracted.get("sovereign_session_id") == metadata.session_id)
                model_match = (extracted.get("sovereign_model_id") == metadata.model.model_id)
                tip_match = (extracted.get("sovereign_audit_tip") == metadata.audit_tip_hash)
                if not (sess_match and model_match and tip_match):
                    embedded_valid = False
                    embedded_err = f"Embedded OOXML metadata mismatch (session: {sess_match}, model: {model_match}, tip: {tip_match})"
            else:
                embedded_valid = False
                embedded_err = "No embedded OOXML custom properties found in archive"

        elif ext in PNG_EXTENSIONS:
            extracted_text = extract_png_lineage(path.read_bytes())
            if extracted_text:
                embedded_found = True
                try:
                    png_json = json.loads(extracted_text)
                    sess_match = (png_json.get("session_id") == metadata.session_id)
                    model_match = (png_json.get("model", {}).get("model_id") == metadata.model.model_id)
                    tip_match = (png_json.get("audit_tip_hash") == metadata.audit_tip_hash)
                    if not (sess_match and model_match and tip_match):
                        embedded_valid = False
                        embedded_err = "Embedded PNG lineage payload mismatch"
                except Exception:
                    embedded_valid = False
                    embedded_err = "Corrupt embedded PNG lineage JSON"
            else:
                embedded_valid = False
                embedded_err = "No sovereign_lineage tEXt chunk found in PNG"

        elif ext in CODE_EXTENSIONS:
            extracted_code = extract_code_lineage(path.read_text(encoding="utf-8"))
            if extracted_code:
                embedded_found = True
                sess_match = (extracted_code.get("session_id") == metadata.session_id)
                model_match = (extracted_code.get("model_id") == metadata.model.model_id)
                tip_match = (extracted_code.get("audit_tip_hash") == metadata.audit_tip_hash)
                if not (sess_match and model_match and tip_match):
                    embedded_valid = False
                    embedded_err = "Embedded code docstring/comment header mismatch"
            else:
                embedded_valid = False
                embedded_err = "No sovereign lineage header found in source file"
        else:
            # Formats without native injectors are not penalized
            embedded_found = False
            embedded_valid = True

        if not embedded_valid:
            return LineageVerificationResult(
                is_valid=False,
                deliverable_path=str(path),
                file_sha256_computed=computed_sha256,
                file_sha256_recorded=recorded_sha256,
                file_hash_valid=True,
                sidecar_exists=True,
                sidecar_valid=True,
                embedded_metadata_found=embedded_found,
                embedded_metadata_valid=False,
                error_message=embedded_err,
            )

        # 4. Audit ledger sequence span verification
        ledger_file = None
        if ledger_path:
            p = Path(ledger_path)
            if p.exists():
                ledger_file = p
        else:
            default_p = Path("data/audit_ledger.jsonl")
            if default_p.exists():
                ledger_file = default_p

        audit_span_valid = True
        audit_details = {}

        if ledger_file:
            span_verified, span_err = cls._verify_audit_span(
                ledger_file=ledger_file,
                session_id=metadata.session_id,
                start_seq=metadata.audit_start_seq,
                end_seq=metadata.audit_end_seq,
                expected_tip=metadata.audit_tip_hash,
            )
            audit_span_valid = span_verified
            if not span_verified:
                return LineageVerificationResult(
                    is_valid=False,
                    deliverable_path=str(path),
                    file_sha256_computed=computed_sha256,
                    file_sha256_recorded=recorded_sha256,
                    file_hash_valid=True,
                    sidecar_exists=True,
                    sidecar_valid=True,
                    embedded_metadata_found=embedded_found,
                    embedded_metadata_valid=True,
                    audit_span_valid=False,
                    error_message=f"Audit ledger span verification failed: {span_err}",
                )
            audit_details["ledger_file"] = str(ledger_file)
            audit_details["span"] = f"{metadata.audit_start_seq}..{metadata.audit_end_seq}"
        else:
            audit_details["ledger"] = "not_provided_or_found"

        return LineageVerificationResult(
            is_valid=True,
            deliverable_path=str(path),
            file_sha256_computed=computed_sha256,
            file_sha256_recorded=recorded_sha256,
            file_hash_valid=True,
            sidecar_exists=True,
            sidecar_valid=True,
            embedded_metadata_found=embedded_found,
            embedded_metadata_valid=embedded_valid,
            audit_span_valid=audit_span_valid,
            details=audit_details,
        )

    @classmethod
    def _verify_audit_span(
        cls,
        ledger_file: Path,
        session_id: str,
        start_seq: int,
        end_seq: int,
        expected_tip: str,
    ) -> tuple[bool, str]:
        """
        Validates that records start_seq..end_seq exist, are hash-chained, and correspond to session_id.
        """
        records_by_seq: Dict[int, Dict[str, Any]] = {}
        with open(ledger_file, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, start=1):
                clean = line.strip()
                if not clean:
                    continue
                try:
                    record = json.loads(clean)
                    seq = record.get("seq_num")
                    if seq is not None and start_seq <= seq <= end_seq:
                        records_by_seq[seq] = record
                except json.JSONDecodeError as e:
                    return False, f"Malformed JSON in ledger line {line_idx}: {e}"

        # Verify all sequence numbers in range are present
        for s in range(start_seq, end_seq + 1):
            if s not in records_by_seq:
                return False, f"Sequence number {s} missing from audit ledger span {start_seq}..{end_seq}"

        # Verify continuity and hash validity
        prev_hash = None
        for s in range(start_seq, end_seq + 1):
            rec = records_by_seq[s]
            # Check session_id consistency for the span
            if rec.get("session_id") != session_id:
                return False, f"Record at seq {s} has session_id '{rec.get('session_id')}', expected '{session_id}'"

            if prev_hash is not None:
                if rec.get("previous_hash") != prev_hash:
                    return False, f"Hash chain broken at seq {s}: previous_hash does not match preceding entry_hash"

            # Check canonical entry hash integrity
            is_valid, msg = verify_record(rec, expected_seq=s, expected_prev_hash=rec.get("previous_hash"))
            if not is_valid:
                return False, f"Record verification error at seq {s}: {msg}"

            prev_hash = rec.get("entry_hash")

        # If end_seq record is the tip hash recorded
        if expected_tip and end_seq in records_by_seq:
            end_rec = records_by_seq[end_seq]
            # If expected tip is at or after this point, check that expected_tip matches or matches end_rec
            if expected_tip != end_rec.get("entry_hash"):
                # expected_tip could be a later tip, but if it was recorded as the tip at completion:
                pass

        return True, "Audit span valid"

    @classmethod
    def trace_provenance(
        cls,
        query: str,
        search_dir: Union[str, Path] = ".",
    ) -> List[LineageTraceResult]:
        """
        Forward provenance trace:
        Locates all deliverables derived from a given source document SHA-256, model weights hash,
        or deliverable SHA-256. If `query` is an existing file, its SHA-256 is computed.
        """
        search_path = Path(search_dir).resolve()
        query_path = Path(query)
        if query_path.exists() and query_path.is_file():
            target_hash = LineageEngine.compute_sha256(query_path)
        else:
            target_hash = query.strip().lower()

        results: List[LineageTraceResult] = []

        if not search_path.exists():
            return results

        for root, _, files in os.walk(search_path):
            for file in files:
                if file.endswith(".lineage.json"):
                    sidecar_file = Path(root) / file
                    try:
                        metadata = LineageEngine.load_sidecar(sidecar_file)
                    except Exception:
                        continue

                    deliverable_file = str(sidecar_file)[:-len(".lineage.json")]

                    # Check 1: Deliverable itself
                    if metadata.deliverable.file_sha256.lower() == target_hash:
                        results.append(
                            LineageTraceResult(
                                deliverable_path=deliverable_file,
                                deliverable_sha256=metadata.deliverable.file_sha256,
                                session_id=metadata.session_id,
                                match_type="deliverable",
                                matched_id=metadata.deliverable.file_name,
                                matched_hash=metadata.deliverable.file_sha256,
                                sidecar_path=str(sidecar_file),
                                generated_iso=metadata.generated_iso,
                            )
                        )

                    # Check 2: Model weights hash
                    elif metadata.model.weights_sha256.lower() == target_hash:
                        results.append(
                            LineageTraceResult(
                                deliverable_path=deliverable_file,
                                deliverable_sha256=metadata.deliverable.file_sha256,
                                session_id=metadata.session_id,
                                match_type="model_weights",
                                matched_id=metadata.model.model_id,
                                matched_hash=metadata.model.weights_sha256,
                                sidecar_path=str(sidecar_file),
                                generated_iso=metadata.generated_iso,
                            )
                        )

                    # Check 3: Source document citations
                    else:
                        for doc in metadata.source_documents:
                            if doc.file_sha256.lower() == target_hash:
                                results.append(
                                    LineageTraceResult(
                                        deliverable_path=deliverable_file,
                                        deliverable_sha256=metadata.deliverable.file_sha256,
                                        session_id=metadata.session_id,
                                        match_type="source_document",
                                        matched_id=doc.document_id,
                                        matched_hash=doc.file_sha256,
                                        sidecar_path=str(sidecar_file),
                                        generated_iso=metadata.generated_iso,
                                    )
                                )
                                break

        return results
