"""
src/sovereign/audit/verifier.py
Comprehensive cryptographic chain verifier and runtime tip-hash verification guard.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sovereign.audit.canonical import GENESIS_PREVIOUS_HASH, verify_record


class AuditTamperException(Exception):
    """Raised when the cryptographic audit chain verification detects tampering or corruption."""
    pass


@dataclass
class VerificationResult:
    """Detailed diagnostic outcome of an audit ledger verification run."""
    is_valid: bool
    records_checked: int
    error_seq: Optional[int] = None
    error_message: Optional[str] = None
    tip_hash: Optional[str] = None


def verify_ledger(ledger_path: str | Path) -> VerificationResult:
    """
    Traverses the entire audit ledger from sequence 0 to the tip.
    Re-computes RFC 8785 canonical bytes and SHA-256 entry hashes,
    verifying strict continuous sequence numbering and unbroken chaining.
    """
    path = Path(ledger_path).resolve()
    if not path.exists() or path.stat().st_size == 0:
        return VerificationResult(
            is_valid=True,
            records_checked=0,
            tip_hash=GENESIS_PREVIOUS_HASH,
        )

    expected_seq = 0
    expected_prev_hash = GENESIS_PREVIOUS_HASH
    tip_hash = GENESIS_PREVIOUS_HASH

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue

            try:
                record = json.loads(line_str)
            except json.JSONDecodeError as exc:
                return VerificationResult(
                    is_valid=False,
                    records_checked=expected_seq,
                    error_seq=expected_seq,
                    error_message=f"JSON parse error at line {line_num}: {exc}",
                )

            is_valid, msg = verify_record(record, expected_seq=expected_seq, expected_prev_hash=expected_prev_hash)
            if not is_valid:
                return VerificationResult(
                    is_valid=False,
                    records_checked=expected_seq,
                    error_seq=expected_seq,
                    error_message=f"Validation failed at line {line_num} (seq {expected_seq}): {msg}",
                )

            tip_hash = record["entry_hash"]
            expected_prev_hash = tip_hash
            expected_seq += 1

    return VerificationResult(
        is_valid=True,
        records_checked=expected_seq,
        tip_hash=tip_hash,
    )


def verify_ledger_tip(ledger_path: str | Path) -> Tuple[bool, str, Optional[str]]:
    """
    Ultra-fast runtime check (< 5ms) inspecting only the final records of the ledger.
    Guarantees the ledger tip is unbroken before acquiring write locks or on warm startup.

    Returns:
        Tuple of (is_valid: bool, status_message: str, tip_hash: Optional[str])
    """
    path = Path(ledger_path).resolve()
    if not path.exists() or path.stat().st_size == 0:
        return True, "Empty ledger", GENESIS_PREVIOUS_HASH

    # Read the last two non-empty lines from the end of the file
    # For small files, standard reverse read or seek from end
    lines: List[str] = []
    file_size = path.stat().st_size
    buffer_size = min(file_size, 32768)

    with open(path, "rb") as f:
        f.seek(file_size - buffer_size)
        content = f.read().decode("utf-8", errors="replace")
        split_lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        lines = split_lines[-2:] if len(split_lines) >= 2 else split_lines

    if not lines:
        return True, "Empty ledger", GENESIS_PREVIOUS_HASH

    if len(lines) == 1:
        # Genesis record only
        try:
            rec = json.loads(lines[0])
            is_valid, msg = verify_record(rec, expected_seq=0, expected_prev_hash=GENESIS_PREVIOUS_HASH)
            if not is_valid:
                return False, f"Genesis tip corruption: {msg}", None
            return True, "Tip valid (genesis)", rec["entry_hash"]
        except Exception as exc:
            return False, f"Failed to parse genesis tip: {exc}", None

    # Two records: prev_record and tip_record
    try:
        prev_rec = json.loads(lines[0])
        tip_rec = json.loads(lines[1])
    except Exception as exc:
        return False, f"Failed to parse tail records: {exc}", None

    expected_tip_seq = prev_rec.get("seq_num", -1) + 1
    expected_prev_hash = prev_rec.get("entry_hash", "")

    is_valid, msg = verify_record(tip_rec, expected_seq=expected_tip_seq, expected_prev_hash=expected_prev_hash)
    if not is_valid:
        return False, f"Tip corruption: {msg}", None

    return True, "Tip valid", tip_rec["entry_hash"]
