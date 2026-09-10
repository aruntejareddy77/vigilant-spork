"""
tests/test_orchestration/test_hitl_interrupt.py
Unit and integration tests for Human-in-the-Loop (HITL) interrupt and resume flow.
"""
import json
from pathlib import Path
import pytest
from sovereign.orchestration.state import GraphState
from sovereign.orchestration.graph import StateGraph, END
from sovereign.orchestration.checkpointer import SQLiteCheckpointer
from sovereign.orchestration.runtime import AgentRuntime, interrupt, GraphInterrupt
from sovereign.audit.ledger import AuditLedger


def test_interrupt_helper_raises():
    """Verify that interrupt() raises GraphInterrupt with payload."""
    with pytest.raises(GraphInterrupt) as excinfo:
        interrupt({"action": "sign_contract", "level": "critical"})
    assert excinfo.value.payload == {"action": "sign_contract", "level": "critical"}


def test_hitl_suspension_and_approval_flow(tmp_path: Path):
    """Test full cycle: run -> suspend -> approve -> resume -> complete with audit trail."""
    db_file = tmp_path / "hitl.sqlite"
    ledger_file = tmp_path / "audit.jsonl"

    checkpointer = SQLiteCheckpointer(db_file)
    ledger = AuditLedger(ledger_file)

    def prepare_data(state: GraphState):
        return {"values": {"data": "analyzed"}}

    def review_gate(state: GraphState):
        interrupt({"action": "approve_data_release", "record_id": "REC-991"})

    def final_publish(state: GraphState):
        return {"values": {"published": True}}

    builder = StateGraph()
    builder.add_node("prepare", prepare_data)
    builder.add_node("gate", review_gate)
    builder.add_node("publish", final_publish)
    builder.set_entry_point("prepare")
    builder.add_edge("prepare", "gate")
    builder.add_edge("gate", "publish")
    builder.add_edge("publish", END)

    runtime = AgentRuntime(builder, checkpointer=checkpointer, audit_ledger=ledger)

    thread_id = "wf-hitl-001"
    initial_state = GraphState(thread_id=thread_id)

    # 1. Run until suspension
    suspended_state = runtime.run(initial_state)
    assert suspended_state.status == "SUSPENDED"
    assert suspended_state.pending_approval == {
        "action": "approve_data_release",
        "record_id": "REC-991",
    }
    assert "published" not in suspended_state.values

    # Verify checkpointer stored suspended state
    cp_state = checkpointer.get_latest_checkpoint(thread_id)
    assert cp_state is not None
    assert cp_state.status == "SUSPENDED"

    # Verify audit event for APPROVAL_REQUIRED
    with open(ledger_file, "r", encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]
    assert len(events) == 1
    assert events[0]["event_type"] == "APPROVAL_REQUIRED"

    # 2. Operator reviews and approves
    completed_state = runtime.resume(
        thread_id=thread_id,
        decision="approve",
        notes="All refinery thresholds verified",
        actor_role="lead_engineer",
    )

    assert completed_state.status == "COMPLETED"
    assert completed_state.values["published"] is True
    assert completed_state.values["approval"]["status"] == "approved"
    assert completed_state.values["approval"]["actor_role"] == "lead_engineer"

    # Verify audit event for APPROVAL_GRANTED
    with open(ledger_file, "r", encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]
    assert len(events) == 2
    assert events[1]["event_type"] == "APPROVAL_GRANTED"
    assert events[1]["actor_role"] == "lead_engineer"

    # Clean up checkpointer
    checkpointer.close()


def test_hitl_rejection_flow(tmp_path: Path):
    """Test full cycle: run -> suspend -> reject -> fail with audit trail."""
    db_file = tmp_path / "hitl_rej.sqlite"
    ledger_file = tmp_path / "audit_rej.jsonl"

    checkpointer = SQLiteCheckpointer(db_file)
    ledger = AuditLedger(ledger_file)

    def prepare_data(state: GraphState):
        return {"values": {"data": "ready"}}

    def review_gate(state: GraphState):
        interrupt({"action": "deploy_config"})

    def execute_deployment(state: GraphState):
        return {"values": {"deployed": True}}

    builder = StateGraph()
    builder.add_node("prepare", prepare_data)
    builder.add_node("gate", review_gate)
    builder.add_node("deploy", execute_deployment)
    builder.set_entry_point("prepare")
    builder.add_edge("prepare", "gate")
    builder.add_edge("gate", "deploy")
    builder.add_edge("deploy", END)

    runtime = AgentRuntime(builder, checkpointer=checkpointer, audit_ledger=ledger)

    thread_id = "wf-hitl-002"
    runtime.run(GraphState(thread_id=thread_id))

    # Reject
    rejected_state = runtime.resume(
        thread_id=thread_id,
        decision="reject",
        notes="Security baseline check failed",
        actor_role="auditor",
    )

    assert rejected_state.status == "FAILED"
    assert "Security baseline check failed" in (rejected_state.last_error or "")
    assert rejected_state.values.get("deployed") is None

    # Check audit ledger
    with open(ledger_file, "r", encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]
    assert len(events) == 2
    assert events[0]["event_type"] == "APPROVAL_REQUIRED"
    assert events[1]["event_type"] == "APPROVAL_REJECTED"

    checkpointer.close()


def test_resume_validation_errors(tmp_path: Path):
    """Test error handling when resuming completed or non-existent threads."""
    db_file = tmp_path / "hitl_err.sqlite"
    checkpointer = SQLiteCheckpointer(db_file)

    builder = StateGraph()
    builder.add_node("done_node", lambda s: {"status": "COMPLETED"})
    builder.set_entry_point("done_node")
    builder.add_edge("done_node", END)

    runtime = AgentRuntime(builder, checkpointer=checkpointer)

    # 1. Non-existent thread
    with pytest.raises(ValueError, match="No checkpoint found"):
        runtime.resume("ghost-thread", decision="approve")

    # 2. Already completed thread
    runtime.run(GraphState(thread_id="completed-thread"))
    with pytest.raises(ValueError, match="not in SUSPENDED state"):
        runtime.resume("completed-thread", decision="approve")

    # 3. Invalid decision
    checkpointer.save_checkpoint(
        "suspended-thread",
        "gate",
        GraphState(thread_id="suspended-thread", status="SUSPENDED"),
    )
    with pytest.raises(ValueError, match="Invalid decision"):
        runtime.resume("suspended-thread", decision="maybe")

    checkpointer.close()
