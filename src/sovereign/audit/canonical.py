"""
src/sovereign/audit/canonical.py
Deterministic RFC 8785 Canonical JSON Hashing and Audit Verification.
"""
import hashlib
from typing import Any, Dict, Tuple
import rfc8785

GENESIS_PREVIOUS_HASH = "0" * 64


def canonicalize_and_hash(
    seq_num: int,
    timestamp_iso: str,
    session_id: str,
    event_type: str,
    actor_role: str,
    payload: Dict[str, Any],
    previous_hash: str,
) -> Tuple[Dict[str, Any], str]:
    """
    Constructs the canonical audit dictionary, serializes it using RFC 8785,
    and calculates the SHA-256 entry hash.

    The canonical dict contains exactly 7 fields:
        - actor_role
        - event_type
        - payload
        - previous_hash
        - seq_num
        - session_id
        - timestamp_iso

    Returns:
        Tuple of (full_record_dict_with_entry_hash, entry_hash_hex)
    """
    canonical_dict = {
        "actor_role": actor_role,
        "event_type": event_type,
        "payload": payload,
        "previous_hash": previous_hash,
        "seq_num": seq_num,
        "session_id": session_id,
        "timestamp_iso": timestamp_iso,
    }
    # RFC 8785 dumps produces deterministic canonical UTF-8 bytes
    canonical_bytes = rfc8785.dumps(canonical_dict)
    entry_hash = hashlib.sha256(canonical_bytes).hexdigest()

    full_record = dict(canonical_dict)
    full_record["entry_hash"] = entry_hash
    return full_record, entry_hash


def verify_record(record: Dict[str, Any], expected_seq: int, expected_prev_hash: str) -> Tuple[bool, str]:
    """
    Verifies that an audit record's sequence, previous hash, and entry hash are valid.

    Returns:
        Tuple of (is_valid: bool, reason_or_status: str)
    """
    seq_num = record.get("seq_num")
    if seq_num != expected_seq:
        return False, f"Sequence mismatch: expected {expected_seq}, got {seq_num}"

    prev_hash = record.get("previous_hash")
    if prev_hash != expected_prev_hash:
        return False, f"Previous hash mismatch at seq {expected_seq}: expected {expected_prev_hash}, got {prev_hash}"

    claimed_entry_hash = record.get("entry_hash")
    if not claimed_entry_hash:
        return False, f"Missing entry_hash at seq {expected_seq}"

    try:
        canonical_dict = {
            "actor_role": record["actor_role"],
            "event_type": record["event_type"],
            "payload": record["payload"],
            "previous_hash": record["previous_hash"],
            "seq_num": record["seq_num"],
            "session_id": record["session_id"],
            "timestamp_iso": record["timestamp_iso"],
        }
        canonical_bytes = rfc8785.dumps(canonical_dict)
        computed_hash = hashlib.sha256(canonical_bytes).hexdigest()
    except KeyError as exc:
        return False, f"Missing required canonical field at seq {expected_seq}: {exc}"
    except Exception as exc:
        return False, f"Canonicalization error at seq {expected_seq}: {exc}"

    if computed_hash != claimed_entry_hash:
        return False, f"Tamper detected at seq {expected_seq}: computed {computed_hash} != stored {claimed_entry_hash}"

    return True, "Valid"
