"""
tests/test_audit/test_ledger.py
Unit tests for process-safe append-only JSONL audit ledger.
"""
import concurrent.futures
import json
from pathlib import Path
from sovereign.audit.canonical import GENESIS_PREVIOUS_HASH, verify_record
from sovereign.audit.ledger import AuditLedger


def test_ledger_initialization_and_append(temp_dir: Path, sample_payload: dict):
    """Verify creating a ledger and appending sequential events."""
    ledger_path = temp_dir / "audit_ledger.jsonl"
    ledger = AuditLedger(ledger_path)

    evt0 = ledger.append_event(
        session_id="session-init",
        event_type="system_startup",
        actor_role="system",
        payload={"status": "ready"},
    )
    assert evt0.seq_num == 0
    assert evt0.previous_hash == GENESIS_PREVIOUS_HASH
    assert len(evt0.entry_hash) == 64

    evt1 = ledger.append_event(
        session_id="session-init",
        event_type="user_action",
        actor_role="admin",
        payload=sample_payload,
    )
    assert evt1.seq_num == 1
    assert evt1.previous_hash == evt0.entry_hash
    assert len(evt1.entry_hash) == 64

    # Verify JSONL lines on disk
    with open(ledger_path, "r", encoding="utf-8") as f:
        lines = [json.loads(line.strip()) for line in f if line.strip()]

    assert len(lines) == 2
    assert lines[0]["seq_num"] == 0
    assert lines[1]["seq_num"] == 1
    assert lines[1]["previous_hash"] == lines[0]["entry_hash"]


def test_ledger_continuity_across_instances(temp_dir: Path):
    """Verify that a new AuditLedger instance re-opens the file and continues the chain seamlessly."""
    ledger_path = temp_dir / "audit_ledger.jsonl"

    ledger1 = AuditLedger(ledger_path)
    evt0 = ledger1.append_event("s1", "event_0", "role_a", {"val": 0})
    evt1 = ledger1.append_event("s1", "event_1", "role_a", {"val": 1})

    # New instance targeting same path
    ledger2 = AuditLedger(ledger_path)
    evt2 = ledger2.append_event("s2", "event_2", "role_b", {"val": 2})

    assert evt2.seq_num == 2
    assert evt2.previous_hash == evt1.entry_hash

    # Verify whole chain on disk
    with open(ledger_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    prev = GENESIS_PREVIOUS_HASH
    for i, rec in enumerate(records):
        valid, msg = verify_record(rec, expected_seq=i, expected_prev_hash=prev)
        assert valid is True, f"Failed at seq {i}: {msg}"
        prev = rec["entry_hash"]


def test_concurrent_ledger_writes(temp_dir: Path):
    """Verify thread-safe concurrent writes maintain strict contiguous sequence numbers and valid chain."""
    ledger_path = temp_dir / "audit_ledger.jsonl"
    ledger = AuditLedger(ledger_path)

    total_events = 20

    def write_worker(idx: int):
        return ledger.append_event(
            session_id=f"session-thread-{idx % 4}",
            event_type="concurrent_write",
            actor_role="worker",
            payload={"worker_idx": idx},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(write_worker, i) for i in range(total_events)]
        concurrent.futures.wait(futures)

    # Read and verify all records
    with open(ledger_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    assert len(records) == total_events

    # Verify contiguous sequence numbering 0..total_events-1
    seqs = [r["seq_num"] for r in records]
    assert seqs == list(range(total_events))

    # Verify unbroken hash chain
    prev = GENESIS_PREVIOUS_HASH
    for i, rec in enumerate(records):
        valid, msg = verify_record(rec, expected_seq=i, expected_prev_hash=prev)
        assert valid is True, f"Chain corrupted at index {i}: {msg}"
        prev = rec["entry_hash"]
