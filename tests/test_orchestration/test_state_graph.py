"""
tests/test_orchestration/test_state_graph.py
Unit tests for deterministic StateGraph runtime and GraphState execution bounds.
"""
import pytest
from sovereign.orchestration.state import GraphState
from sovereign.orchestration.graph import StateGraph, GraphInterrupt, END


def test_linear_graph_execution():
    """Test standard sequential multi-step execution."""
    def step_one(state: GraphState):
        msgs = list(state.messages)
        msgs.append({"role": "system", "content": "Step 1 executed"})
        return {"messages": msgs, "values": {"stage": 1}}

    def step_two(state: GraphState):
        msgs = list(state.messages)
        msgs.append({"role": "system", "content": "Step 2 executed"})
        stage = state.values.get("stage", 0) + 1
        return {"messages": msgs, "values": {"stage": stage}}

    builder = StateGraph()
    builder.add_node("step_one", step_one)
    builder.add_node("step_two", step_two)
    builder.set_entry_point("step_one")
    builder.add_edge("step_one", "step_two")
    builder.add_edge("step_two", END)

    compiled = builder.compile()
    initial_state = GraphState(thread_id="test-linear-01")
    final_state = compiled.invoke(initial_state)

    assert final_state.status == "COMPLETED"
    assert final_state.step_count == 2
    assert len(final_state.messages) == 2
    assert final_state.values.get("stage") == 2
    assert final_state.last_error is None


def test_conditional_branching():
    """Test conditional edge routing based on state inspection."""
    def classify_task(state: GraphState):
        query = state.values.get("query", "")
        branch = "code" if "code" in query else "text"
        return {"values": {"branch": branch}}

    def handle_code(state: GraphState):
        return {"values": {"result": "code_processed"}}

    def handle_text(state: GraphState):
        return {"values": {"result": "text_processed"}}

    def route_task(state: GraphState) -> str:
        return state.values.get("branch", "text")

    builder = StateGraph()
    builder.add_node("classify", classify_task)
    builder.add_node("handle_code", handle_code)
    builder.add_node("handle_text", handle_text)
    builder.set_entry_point("classify")

    builder.add_conditional_edges(
        "classify",
        route_task,
        {"code": "handle_code", "text": "handle_text"},
    )
    builder.add_edge("handle_code", END)
    builder.add_edge("handle_text", END)

    compiled = builder.compile()

    # Branch 1: code
    state_code = compiled.invoke({"thread_id": "c1", "values": {"query": "generate code"}})
    assert state_code.status == "COMPLETED"
    assert state_code.values["result"] == "code_processed"

    # Branch 2: text
    state_text = compiled.invoke({"thread_id": "t1", "values": {"query": "write report"}})
    assert state_text.status == "COMPLETED"
    assert state_text.values["result"] == "text_processed"


def test_max_steps_bounding_prevents_runaway_cycles():
    """Test that infinite cyclic graph is bounded strictly by max_steps."""
    def infinite_loop_node(state: GraphState):
        return {"values": {"counter": state.values.get("counter", 0) + 1}}

    builder = StateGraph()
    builder.add_node("looper", infinite_loop_node)
    builder.set_entry_point("looper")
    builder.add_edge("looper", "looper")  # Infinite cycle

    compiled = builder.compile()
    initial_state = GraphState(thread_id="runaway-01", max_steps=5)
    final_state = compiled.invoke(initial_state)

    assert final_state.status == "FAILED"
    assert final_state.step_count == 5
    assert "Step count exceeded maximum allowed limit" in (final_state.last_error or "")


def test_bounded_self_correction_recovery():
    """Test bounded reflection loop recovering within allowed retry count."""
    attempts = 0

    def faulty_node(state: GraphState):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            # Simulate transient failure
            return {"last_error": f"Flaky error on attempt {attempts}"}
        return {"last_error": None, "values": {"recovered": True}}

    def reflect_and_fix(state: GraphState):
        # Reflection node formats context and increments retry count
        return {"retry_count": state.retry_count + 1}

    def error_router(state: GraphState) -> str:
        if state.last_error is None:
            return "success"
        if state.retry_count < state.max_retries:
            return "retry"
        return "escalate"

    def failure_escalation(state: GraphState):
        return {"status": "FAILED"}

    builder = StateGraph()
    builder.add_node("faulty", faulty_node)
    builder.add_node("reflect", reflect_and_fix)
    builder.add_node("escalate", failure_escalation)
    builder.set_entry_point("faulty")

    builder.add_conditional_edges(
        "faulty",
        error_router,
        {"retry": "reflect", "success": END, "escalate": "escalate"},
    )
    builder.add_edge("reflect", "faulty")
    builder.add_edge("escalate", END)

    compiled = builder.compile()
    initial = GraphState(thread_id="retry-success", max_retries=3)
    final = compiled.invoke(initial)

    assert final.status == "COMPLETED"
    assert final.values.get("recovered") is True
    assert final.retry_count == 2
    assert final.last_error is None


def test_bounded_self_correction_exhaustion():
    """Test bounded reflection loop exhausting max_retries and escalating to failure."""
    def persistent_fault(state: GraphState):
        return {"last_error": "Permanent syntax failure"}

    def reflect_and_fix(state: GraphState):
        return {"retry_count": state.retry_count + 1}

    def error_router(state: GraphState) -> str:
        if state.last_error is None:
            return "success"
        if state.retry_count < state.max_retries:
            return "retry"
        return "escalate"

    def failure_escalation(state: GraphState):
        return {"status": "FAILED", "values": {"escalated_to_human": True}}

    builder = StateGraph()
    builder.add_node("faulty", persistent_fault)
    builder.add_node("reflect", reflect_and_fix)
    builder.add_node("escalate", failure_escalation)
    builder.set_entry_point("faulty")

    builder.add_conditional_edges(
        "faulty",
        error_router,
        {"retry": "reflect", "success": END, "escalate": "escalate"},
    )
    builder.add_edge("reflect", "faulty")
    builder.add_edge("escalate", END)

    compiled = builder.compile()
    initial = GraphState(thread_id="retry-exhaust", max_retries=3)
    final = compiled.invoke(initial)

    assert final.status == "FAILED"
    assert final.values.get("escalated_to_human") is True
    assert final.retry_count == 3
    assert final.last_error == "Permanent syntax failure"


def test_graph_interrupt_suspension():
    """Test that GraphInterrupt halts execution and sets status to SUSPENDED."""
    def draft_deliverable(state: GraphState):
        return {"values": {"draft": "Report V1"}}

    def approval_gate(state: GraphState):
        raise GraphInterrupt({"action": "generate_report", "doc_type": "pdf"})

    def publish_deliverable(state: GraphState):
        return {"values": {"published": True}}

    builder = StateGraph()
    builder.add_node("draft", draft_deliverable)
    builder.add_node("gate", approval_gate)
    builder.add_node("publish", publish_deliverable)
    builder.set_entry_point("draft")
    builder.add_edge("draft", "gate")
    builder.add_edge("gate", "publish")
    builder.add_edge("publish", END)

    compiled = builder.compile()
    result = compiled.invoke({"thread_id": "interrupt-01"})

    assert result.status == "SUSPENDED"
    assert result.pending_approval == {"action": "generate_report", "doc_type": "pdf"}
    assert result.values.get("draft") == "Report V1"
    assert "published" not in result.values


def test_invalid_graph_compilation_errors():
    """Test validation errors during compile."""
    builder = StateGraph()
    with pytest.raises(ValueError, match="entry point must be set"):
        builder.compile()

    builder.set_entry_point("missing_node")
    with pytest.raises(ValueError, match="not found in registered nodes"):
        builder.compile()
