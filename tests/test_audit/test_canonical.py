"""
tests/test_audit/test_canonical.py
Unit tests for RFC 8785 deterministic canonical serialization and hashing.
"""
import hashlib
import rfc8785
from sovereign.audit.canonical import GENESIS_PREVIOUS_HASH, canonicalize_and_hash, verify_record


def test_genesis_previous_hash_constant():
    """Verify genesis previous hash is exactly 64 zeros."""
    assert GENESIS_PREVIOUS_HASH == "0" * 64
    assert len(GENESIS_PREVIOUS_HASH) == 64


def test_key_ordering_invariance():
    """Verify that different key ordering in payload results in identical RFC 8785 canonical bytes."""
    payload_a = {"z": 100, "a": "first", "m": [3, 2, 1], "sub": {"beta": 2, "alpha": 1}}
    payload_b = {"a": "first", "sub": {"alpha": 1, "beta": 2}, "m": [3, 2, 1], "z": 100}

    record_a, hash_a = canonicalize_and_hash(
        seq_num=0,
        timestamp_iso="2026-09-10T10:00:00Z",
        session_id="session-1",
        event_type="test_event",
        actor_role="system",
        payload=payload_a,
        previous_hash=GENESIS_PREVIOUS_HASH,
    )

    record_b, hash_b = canonicalize_and_hash(
        seq_num=0,
        timestamp_iso="2026-09-10T10:00:00Z",
        session_id="session-1",
        event_type="test_event",
        actor_role="system",
        payload=payload_b,
        previous_hash=GENESIS_PREVIOUS_HASH,
    )

    assert hash_a == hash_b
    assert record_a["entry_hash"] == record_b["entry_hash"]


def test_unicode_determinism():
    """Verify canonical serialization of complex unicode characters (accented, CJK, emoji)."""
    payload = {
        "hindi": "सम्प्रभुता",
        "japanese": "自己主権型AI",
        "emoji": "🛡️🔒⚡",
        "special": "control\tchars\nand\\escapes",
    }

    record, entry_hash = canonicalize_and_hash(
        seq_num=1,
        timestamp_iso="2026-09-10T10:05:00Z",
        session_id="session-unicode",
        event_type="i18n_test",
        actor_role="operator",
        payload=payload,
        previous_hash=GENESIS_PREVIOUS_HASH,
    )

    # Re-run and assert identical hash
    record_again, hash_again = canonicalize_and_hash(
        seq_num=1,
        timestamp_iso="2026-09-10T10:05:00Z",
        session_id="session-unicode",
        event_type="i18n_test",
        actor_role="operator",
        payload=payload,
        previous_hash=GENESIS_PREVIOUS_HASH,
    )

    assert entry_hash == hash_again
    is_valid, msg = verify_record(record, expected_seq=1, expected_prev_hash=GENESIS_PREVIOUS_HASH)
    assert is_valid is True
    assert msg == "Valid"


def test_float_representation_canonical():
    """Verify float representation adheres to RFC 8785 ECMAScript specification."""
    payload = {
        "float_val": 1.0,
        "scientific": 1e-05,
        "pi_approx": 3.141592653589793,
    }
    raw_bytes = rfc8785.dumps(payload)
    # RFC 8785 specifies 1.0 serializes as 1 (integer format when no fractional part)
    assert b'"float_val":1' in raw_bytes


def test_verify_record_validation():
    """Verify validation logic catches sequence, previous_hash, and payload tampering."""
    record, entry_hash = canonicalize_and_hash(
        seq_num=5,
        timestamp_iso="2026-09-10T10:10:00Z",
        session_id="session-5",
        event_type="login",
        actor_role="auditor",
        payload={"ip": "127.0.0.1"},
        previous_hash="a" * 64,
    )

    # Valid check
    valid, msg = verify_record(record, expected_seq=5, expected_prev_hash="a" * 64)
    assert valid is True

    # Sequence mismatch
    valid, msg = verify_record(record, expected_seq=6, expected_prev_hash="a" * 64)
    assert valid is False
    assert "Sequence mismatch" in msg

    # Previous hash mismatch
    valid, msg = verify_record(record, expected_seq=5, expected_prev_hash="b" * 64)
    assert valid is False
    assert "Previous hash mismatch" in msg

    # Payload tampering
    tampered_record = dict(record)
    tampered_record["payload"] = {"ip": "192.168.1.1"}
    valid, msg = verify_record(tampered_record, expected_seq=5, expected_prev_hash="a" * 64)
    assert valid is False
    assert "Tamper detected" in msg
