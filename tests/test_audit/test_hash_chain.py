"""
tests/test_audit/test_hash_chain.py
Unit tests for cryptographic hash chaining and single-byte tamper detection.
"""
from typing import List, Dict, Any
from sovereign.audit.canonical import GENESIS_PREVIOUS_HASH, canonicalize_and_hash, verify_record


def generate_chain(length: int) -> List[Dict[str, Any]]:
    """Helper to generate a valid hash chain of specified length."""
    chain = []
    prev_hash = GENESIS_PREVIOUS_HASH
    for i in range(length):
        rec, entry_hash = canonicalize_and_hash(
            seq_num=i,
            timestamp_iso=f"2026-09-10T10:{i:02d}:00Z",
            session_id="test-session",
            event_type="action_step",
            actor_role="agent",
            payload={"step": i, "result": f"output_{i}"},
            previous_hash=prev_hash,
        )
        chain.append(rec)
        prev_hash = entry_hash
    return chain


def test_valid_hash_chain():
    """Verify that a standard sequential chain passes full verification."""
    chain = generate_chain(10)
    assert len(chain) == 10

    prev_hash = GENESIS_PREVIOUS_HASH
    for i, record in enumerate(chain):
        is_valid, msg = verify_record(record, expected_seq=i, expected_prev_hash=prev_hash)
        assert is_valid is True, f"Record {i} failed verification: {msg}"
        prev_hash = record["entry_hash"]


def test_single_byte_payload_tamper_detection():
    """Verify that mutating even one character in an intermediate payload breaks verification."""
    chain = generate_chain(10)

    # Tamper with record 4
    chain[4]["payload"]["result"] = "output_4_tampered"

    prev_hash = GENESIS_PREVIOUS_HASH
    tamper_detected_at = None

    for i, record in enumerate(chain):
        is_valid, msg = verify_record(record, expected_seq=i, expected_prev_hash=prev_hash)
        if not is_valid:
            tamper_detected_at = i
            break
        prev_hash = record["entry_hash"]

    assert tamper_detected_at == 4


def test_timestamp_tamper_detection():
    """Verify that altering timestamp string breaks canonical hash verification."""
    chain = generate_chain(5)

    # Tamper with record 2 timestamp
    chain[2]["timestamp_iso"] = "2026-09-10T10:02:01Z"

    is_valid, msg = verify_record(chain[2], expected_seq=2, expected_prev_hash=chain[1]["entry_hash"])
    assert is_valid is False
    assert "Tamper detected at seq 2" in msg


def test_record_deletion_breaks_chain():
    """Verify that deleting an intermediate record breaks the sequence and previous_hash."""
    chain = generate_chain(6)

    # Delete record at index 3
    deleted_chain = chain[:3] + chain[4:]

    # Check record that now sits at index 3 (was original index 4)
    # It has seq_num 4, but expected_seq is 3
    is_valid, msg = verify_record(deleted_chain[3], expected_seq=3, expected_prev_hash=deleted_chain[2]["entry_hash"])
    assert is_valid is False
    assert "Sequence mismatch: expected 3, got 4" in msg


def test_reorder_records_breaks_chain():
    """Verify that swapping two records breaks verification immediately."""
    chain = generate_chain(5)

    # Swap record 1 and record 2
    chain[1], chain[2] = chain[2], chain[1]

    is_valid, msg = verify_record(chain[1], expected_seq=1, expected_prev_hash=chain[0]["entry_hash"])
    assert is_valid is False
