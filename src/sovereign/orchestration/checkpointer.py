"""
src/sovereign/orchestration/checkpointer.py
SQLite-based state persistence engine with Write-Ahead Logging (WAL) per D-29.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Union
from sovereign.orchestration.state import GraphState


class SQLiteCheckpointer:
    """
    Persists agent workflow session states to SQLite with WAL mode.
    Provides crash recovery and time-travel inspection of execution checkpoints.
    """

    def __init__(self, db_path: Union[str, Path] = "agent_state.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=10.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Initialize WAL mode and create tables if they do not exist."""
        with self._conn:
            self._conn.execute("PRAGMA journal_mode = WAL;")
            self._conn.execute("PRAGMA synchronous = NORMAL;")
            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._conn.execute("PRAGMA busy_timeout = 5000;")

            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id TEXT PRIMARY KEY,
                    created_iso TEXT NOT NULL,
                    updated_iso TEXT NOT NULL,
                    status TEXT NOT NULL
                );
            """)

            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    step_count INTEGER NOT NULL,
                    node_name TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_iso TEXT NOT NULL,
                    FOREIGN KEY (thread_id) REFERENCES threads (thread_id) ON DELETE CASCADE
                );
            """)

            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_checkpoints_thread 
                ON checkpoints (thread_id, checkpoint_id DESC);
            """)

    def save_checkpoint(self, thread_id: str, node_name: str, state: GraphState) -> int:
        """
        Save a state snapshot for a given thread and node transition.
        Upserts the thread summary and appends to checkpoints.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        state_json = state.model_dump_json()

        with self._conn:
            # Upsert thread status
            self._conn.execute(
                """
                INSERT INTO threads (thread_id, created_iso, updated_iso, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    updated_iso = excluded.updated_iso,
                    status = excluded.status;
                """,
                (thread_id, now_iso, now_iso, state.status),
            )

            # Insert checkpoint
            cursor = self._conn.execute(
                """
                INSERT INTO checkpoints (thread_id, step_count, node_name, state_json, created_iso)
                VALUES (?, ?, ?, ?, ?);
                """,
                (thread_id, state.step_count, node_name, state_json, now_iso),
            )
            checkpoint_id = cursor.lastrowid
            if checkpoint_id is None:
                raise RuntimeError("Failed to obtain lastrowid after inserting checkpoint")
            return checkpoint_id

    def get_latest_checkpoint(self, thread_id: str) -> Optional[GraphState]:
        """Retrieve the latest GraphState snapshot for a thread."""
        cursor = self._conn.execute(
            """
            SELECT state_json FROM checkpoints
            WHERE thread_id = ?
            ORDER BY checkpoint_id DESC
            LIMIT 1;
            """,
            (thread_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        state_dict = json.loads(row["state_json"])
        return GraphState(**state_dict)

    def get_checkpoint_by_id(self, checkpoint_id: int) -> Optional[GraphState]:
        """Retrieve a specific GraphState snapshot by checkpoint_id."""
        cursor = self._conn.execute(
            """
            SELECT state_json FROM checkpoints
            WHERE checkpoint_id = ?;
            """,
            (checkpoint_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        state_dict = json.loads(row["state_json"])
        return GraphState(**state_dict)

    def list_thread_checkpoints(self, thread_id: str) -> List[Dict[str, Any]]:
        """List checkpoint history for a thread without payload overhead."""
        cursor = self._conn.execute(
            """
            SELECT checkpoint_id, thread_id, step_count, node_name, created_iso
            FROM checkpoints
            WHERE thread_id = ?
            ORDER BY checkpoint_id ASC;
            """,
            (thread_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_threads(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List tracked workflow threads, optionally filtering by status."""
        if status:
            cursor = self._conn.execute(
                """
                SELECT thread_id, created_iso, updated_iso, status
                FROM threads
                WHERE status = ?
                ORDER BY updated_iso DESC;
                """,
                (status,),
            )
        else:
            cursor = self._conn.execute(
                """
                SELECT thread_id, created_iso, updated_iso, status
                FROM threads
                ORDER BY updated_iso DESC;
                """
            )
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> "SQLiteCheckpointer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
