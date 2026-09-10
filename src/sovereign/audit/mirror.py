"""
src/sovereign/audit/mirror.py
Synchronous SQLite WAL query mirror for high-speed indexing, search, and session slicing.
"""
import json
from pathlib import Path
import sqlite3
from typing import Any, List, Optional
from sovereign.audit.models import AuditEvent


class AuditMirror:
    """
    Manages audit_index.sqlite in WAL mode.
    Provides fast, indexed queries and per-session slice exports while
    the JSONL ledger remains the immutable cryptographic ground truth.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    seq_num INTEGER PRIMARY KEY,
                    timestamp_iso TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_session_id ON audit_events(session_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_events(event_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp_iso);")

    def insert_event(self, event: AuditEvent) -> None:
        """Synchronously inserts a single verified AuditEvent into SQLite."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO audit_events (
                    seq_num, timestamp_iso, session_id, event_type, actor_role, payload_json, previous_hash, entry_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.seq_num,
                    event.timestamp_iso,
                    event.session_id,
                    event.event_type,
                    event.actor_role,
                    json.dumps(event.payload, ensure_ascii=False),
                    event.previous_hash,
                    event.entry_hash,
                ),
            )

    def batch_insert(self, events: List[AuditEvent]) -> None:
        """Batch inserts multiple AuditEvent records within a single transaction."""
        if not events:
            return
        rows = [
            (
                e.seq_num,
                e.timestamp_iso,
                e.session_id,
                e.event_type,
                e.actor_role,
                json.dumps(e.payload, ensure_ascii=False),
                e.previous_hash,
                e.entry_hash,
            )
            for e in events
        ]
        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO audit_events (
                    seq_num, timestamp_iso, session_id, event_type, actor_role, payload_json, previous_hash, entry_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def _row_to_event(self, row: tuple) -> AuditEvent:
        return AuditEvent(
            seq_num=row[0],
            timestamp_iso=row[1],
            session_id=row[2],
            event_type=row[3],
            actor_role=row[4],
            payload=json.loads(row[5]),
            previous_hash=row[6],
            entry_hash=row[7],
        )

    def query_events(
        self,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AuditEvent]:
        """
        Query audit records by session, event type, or timestamp range with pagination.
        """
        query = "SELECT seq_num, timestamp_iso, session_id, event_type, actor_role, payload_json, previous_hash, entry_hash FROM audit_events WHERE 1=1"
        params: List[Any] = []

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if start_time:
            query += " AND timestamp_iso >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp_iso <= ?"
            params.append(end_time)

        query += " ORDER BY seq_num ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_event(row) for row in cursor.fetchall()]

    def export_session_slice(self, session_id: str) -> List[AuditEvent]:
        """
        Extracts all audit events corresponding to a given session_id in sequential order.
        """
        return self.query_events(session_id=session_id, limit=1000000, offset=0)

    def count_events(self, session_id: Optional[str] = None) -> int:
        """Returns total event count, optionally filtered by session."""
        query = "SELECT COUNT(*) FROM audit_events"
        params: List[Any] = []
        if session_id:
            query += " WHERE session_id = ?"
            params.append(session_id)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchone()[0]
