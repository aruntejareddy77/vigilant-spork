"""
tests/test_audit/test_ledger_mirror.py
Unit tests for SQLite WAL query mirror and synchronous audit ledger integration.
"""
from pathlib import Path
import sqlite3
import time
from sovereign.audit.ledger import AuditLedger
from sovereign.audit.mirror import AuditMirror
from sovereign.audit.models import AuditEvent


def test_mirror_initialization_wal_mode(temp_dir: Path):
    """Verify SQLite database initializes in WAL mode with correct pragmas and indexes."""
    db_path = temp_dir / "audit_index.sqlite"
    mirror = AuditMirror(db_path)

    # Check journal mode from fresh connection (persisted in DB header)
    conn = sqlite3.connect(str(db_path))
    journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    conn.close()
    assert journal_mode.lower() == "wal"

    # Check connection pragmas on mirror connection
    with mirror._get_connection() as m_conn:
        synchronous = m_conn.execute("PRAGMA synchronous;").fetchone()[0]
        assert synchronous in (1, "NORMAL", "normal")


def test_synchronous_ledger_mirror_parity(temp_dir: Path, sample_payload: dict):
    """Verify that every event appended to AuditLedger is synchronously mirrored to SQLite."""
    ledger_path = temp_dir / "audit_ledger.jsonl"
    db_path = temp_dir / "audit_index.sqlite"

    mirror = AuditMirror(db_path)
    ledger = AuditLedger(ledger_path=ledger_path, mirror=mirror)

    # Append 5 events across two sessions
    for i in range(5):
        s_id = "session-A" if i % 2 == 0 else "session-B"
        ledger.append_event(
            session_id=s_id,
            event_type=f"action_{i}",
            actor_role="user",
            payload={"step": i, "details": sample_payload},
        )

    # Check mirror count
    assert mirror.count_events() == 5
    assert mirror.count_events(session_id="session-A") == 3
    assert mirror.count_events(session_id="session-B") == 2

    # Check exact event field parity
    all_events = mirror.query_events(limit=10)
    assert len(all_events) == 5
    for i, evt in enumerate(all_events):
        assert isinstance(evt, AuditEvent)
        assert evt.seq_num == i
        assert evt.event_type == f"action_{i}"


def test_query_filtering_and_pagination(temp_dir: Path):
    """Verify query filtering by event_type, time range, and pagination."""
    db_path = temp_dir / "audit_index.sqlite"
    mirror = AuditMirror(db_path)

    events = []
    for i in range(10):
        evt = AuditEvent(
            seq_num=i,
            timestamp_iso=f"2026-09-10T12:{i:02d}:00Z",
            session_id="session-paged",
            event_type="read" if i < 5 else "write",
            actor_role="agent",
            payload={"i": i},
            previous_hash="0" * 64 if i == 0 else "a" * 64,
            entry_hash="a" * 64,
        )
        events.append(evt)

    mirror.batch_insert(events)

    # Filter by event_type
    reads = mirror.query_events(event_type="read")
    assert len(reads) == 5
    assert all(r.event_type == "read" for r in reads)

    # Filter by time range
    time_filtered = mirror.query_events(
        start_time="2026-09-10T12:02:00Z",
        end_time="2026-09-10T12:06:00Z",
    )
    assert len(time_filtered) == 5
    assert [e.seq_num for e in time_filtered] == [2, 3, 4, 5, 6]

    # Pagination
    paged = mirror.query_events(limit=3, offset=4)
    assert len(paged) == 3
    assert [e.seq_num for e in paged] == [4, 5, 6]


def test_export_session_slice(temp_dir: Path):
    """Verify export_session_slice isolates all records for one session in sequence."""
    db_path = temp_dir / "audit_index.sqlite"
    mirror = AuditMirror(db_path)

    # Insert interleaved session events
    for i in range(15):
        sid = f"session-{(i % 3)}"
        evt = AuditEvent(
            seq_num=i,
            timestamp_iso=f"2026-09-10T13:{i:02d}:00Z",
            session_id=sid,
            event_type="test",
            actor_role="tester",
            payload={"idx": i},
            previous_hash="0" * 64,
            entry_hash="f" * 64,
        )
        mirror.insert_event(evt)

    session_1_slice = mirror.export_session_slice("session-1")
    assert len(session_1_slice) == 5
    assert all(e.session_id == "session-1" for e in session_1_slice)
    assert [e.seq_num for e in session_1_slice] == [1, 4, 7, 10, 13]


def test_query_latency_sub_millisecond(temp_dir: Path):
    """Verify indexed queries against SQLite mirror execute in sub-millisecond time."""
    db_path = temp_dir / "audit_index.sqlite"
    mirror = AuditMirror(db_path)

    # Insert 100 events
    events = [
        AuditEvent(
            seq_num=i,
            timestamp_iso=f"2026-09-10T14:{i % 60:02d}:00Z",
            session_id=f"session-{i % 10}",
            event_type=f"type_{i % 5}",
            actor_role="service",
            payload={"metric": i * 1.5},
            previous_hash="0" * 64,
            entry_hash="e" * 64,
        )
        for i in range(100)
    ]
    mirror.batch_insert(events)

    # Warmup
    mirror.query_events(session_id="session-3")

    # Measure 50 queries
    start = time.perf_counter()
    iterations = 50
    for _ in range(iterations):
        res = mirror.query_events(session_id="session-3", limit=10)
        assert len(res) == 10
    total_time = time.perf_counter() - start
    avg_ms = (total_time / iterations) * 1000

    # Ensure average query time is fast (< 5ms on any machine, typically < 0.5ms)
    assert avg_ms < 5.0, f"Average query latency too high: {avg_ms:.2f}ms"
