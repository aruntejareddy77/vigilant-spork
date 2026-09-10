"""
tests/test_orchestration/test_checkpointer.py
Unit and integration tests for SQLiteCheckpointer WAL persistence and session recovery.
"""
from pathlib import Path
import pytest
from sovereign.orchestration.state import GraphState
from sovereign.orchestration.graph import StateGraph, END
from sovereign.orchestration.checkpointer import SQLiteCheckpointer


def test_sqlite_checkpointer_wal_initialization(tmp_path: Path):
    """Test that SQLite database initializes with WAL mode and schema tables."""
    db_file = tmp_path / "test_wal.sqlite"
    with SQLiteCheckpointer(db_file) as cp:
        # Check journal mode
        cursor = cp._conn.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        assert mode.lower() == "wal"

        # Check tables exist
        cursor = cp._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert "threads" in tables
        assert "checkpoints" in tables


def test_save_and_get_checkpoints(tmp_path: Path):
    """Test saving progressive state checkpoints and retrieving the latest snapshot."""
    db_file = tmp_path / "state_flow.sqlite"
    with SQLiteCheckpointer(db_file) as cp:
        thread_id = "thread-alpha-1"
        s1 = GraphState(
            thread_id=thread_id,
            step_count=1,
            status="RUNNING",
            values={"progress": 25},
        )
        cid1 = cp.save_checkpoint(thread_id, "step_one", s1)
        assert cid1 > 0

        s2 = GraphState(
            thread_id=thread_id,
            step_count=2,
            status="RUNNING",
            values={"progress": 50},
        )
        cid2 = cp.save_checkpoint(thread_id, "step_two", s2)
        assert cid2 > cid1

        # Retrieve latest
        latest = cp.get_latest_checkpoint(thread_id)
        assert latest is not None
        assert latest.step_count == 2
        assert latest.values["progress"] == 50

        # Retrieve by specific ID
        snap1 = cp.get_checkpoint_by_id(cid1)
        assert snap1 is not None
        assert snap1.step_count == 1
        assert snap1.values["progress"] == 25


def test_list_thread_checkpoints_and_filtering(tmp_path: Path):
    """Test checkpoint history indexing and thread status filtering."""
    db_file = tmp_path / "threads.sqlite"
    with SQLiteCheckpointer(db_file) as cp:
        # Thread 1: Completed
        cp.save_checkpoint(
            "thread-1",
            "node_a",
            GraphState(thread_id="thread-1", step_count=1, status="COMPLETED"),
        )
        # Thread 2: Suspended (waiting for HITL)
        cp.save_checkpoint(
            "thread-2",
            "approval_gate",
            GraphState(
                thread_id="thread-2",
                step_count=2,
                status="SUSPENDED",
                pending_approval={"action": "export_pdf"},
            ),
        )

        all_threads = cp.list_threads()
        assert len(all_threads) == 2

        suspended_threads = cp.list_threads(status="SUSPENDED")
        assert len(suspended_threads) == 1
        assert suspended_threads[0]["thread_id"] == "thread-2"

        history = cp.list_thread_checkpoints("thread-2")
        assert len(history) == 1
        assert history[0]["node_name"] == "approval_gate"
        assert history[0]["step_count"] == 2


def test_crash_recovery_across_process_restarts(tmp_path: Path):
    """Test that state persists cleanly when checkpointer connection is closed and reopened."""
    db_file = tmp_path / "persistent.sqlite"

    # Session 1: write and close
    cp1 = SQLiteCheckpointer(db_file)
    cp1.save_checkpoint(
        "resilient-thread",
        "task_node",
        GraphState(
            thread_id="resilient-thread",
            step_count=3,
            status="RUNNING",
            values={"interrupted_task": "batch_ocr"},
        ),
    )
    cp1.close()

    # Session 2: reopen same file
    cp2 = SQLiteCheckpointer(db_file)
    recovered = cp2.get_latest_checkpoint("resilient-thread")
    assert recovered is not None
    assert recovered.step_count == 3
    assert recovered.values["interrupted_task"] == "batch_ocr"
    cp2.close()


def test_compiled_graph_auto_checkpointing(tmp_path: Path):
    """Test that CompiledGraph seamlessly commits checkpoints after every step."""
    db_file = tmp_path / "graph_auto.sqlite"
    cp = SQLiteCheckpointer(db_file)

    def node_first(state: GraphState):
        return {"values": {"count": 1}}

    def node_second(state: GraphState):
        return {"values": {"count": state.values["count"] + 1}}

    builder = StateGraph()
    builder.add_node("first", node_first)
    builder.add_node("second", node_second)
    builder.set_entry_point("first")
    builder.add_edge("first", "second")
    builder.add_edge("second", END)

    compiled = builder.compile(checkpointer=cp)
    thread_id = "auto-graph-01"
    final_state = compiled.invoke(GraphState(thread_id=thread_id))

    assert final_state.status == "COMPLETED"
    assert final_state.step_count == 2

    # Verify all checkpoint entries in DB: __start__, first, second, __end__
    history = cp.list_thread_checkpoints(thread_id)
    node_names = [entry["node_name"] for entry in history]
    assert node_names == ["__start__", "first", "second", END]

    latest = cp.get_latest_checkpoint(thread_id)
    assert latest is not None
    assert latest.status == "COMPLETED"
    assert latest.values["count"] == 2

    cp.close()
