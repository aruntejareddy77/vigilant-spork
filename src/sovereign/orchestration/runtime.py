"""
src/sovereign/orchestration/runtime.py
Agent runtime managing graph compilation, step execution, and Human-in-the-Loop (HITL) approval gates.
"""
import json
from typing import Any, Dict, Optional, Union
from sovereign.orchestration.state import GraphState
from sovereign.orchestration.graph import StateGraph, CompiledGraph, GraphInterrupt, END
from sovereign.orchestration.checkpointer import SQLiteCheckpointer
from sovereign.audit.ledger import AuditLedger


def interrupt(payload: Dict[str, Any]) -> None:
    """
    Pause execution within a node to await external input or human approval.
    Raises GraphInterrupt which is caught by CompiledGraph / AgentRuntime.
    """
    raise GraphInterrupt(payload)


class AgentRuntime:
    """
    High-level execution runtime that coordinates StateGraph, SQLite WAL checkpointer,
    and append-only AuditLedger for cryptographic tracking of human approvals and state transitions.
    """

    def __init__(
        self,
        graph: Union[StateGraph, CompiledGraph],
        checkpointer: Optional[SQLiteCheckpointer] = None,
        audit_ledger: Optional[AuditLedger] = None,
    ):
        self.checkpointer = checkpointer
        if isinstance(graph, StateGraph):
            self.compiled = graph.compile(checkpointer=self.checkpointer)
        else:
            self.compiled = graph
            if not self.checkpointer:
                self.checkpointer = self.compiled.checkpointer

        self.audit_ledger = audit_ledger

    def run(self, initial_state: Union[GraphState, Dict[str, Any]]) -> GraphState:
        """
        Execute workflow graph from start. Emits APPROVAL_REQUIRED event if interrupted.
        """
        final_state = self.compiled.invoke(initial_state)

        if final_state.status == "SUSPENDED" and self.audit_ledger:
            self.audit_ledger.append_event(
                session_id=final_state.thread_id,
                event_type="APPROVAL_REQUIRED",
                actor_role="system",
                payload={
                    "thread_id": final_state.thread_id,
                    "step_count": final_state.step_count,
                    "pending_approval": final_state.pending_approval,
                },
            )

        return final_state

    def resume(
        self,
        thread_id: str,
        decision: str,
        notes: Optional[str] = None,
        actor_role: str = "operator",
        resume_node: Optional[str] = None,
    ) -> GraphState:
        """
        Resume an interrupted/suspended workflow thread upon human approval or rejection.
        Emits APPROVAL_GRANTED or APPROVAL_REJECTED to AuditLedger.
        """
        if not self.checkpointer:
            raise RuntimeError("Cannot resume workflow without a configured SQLiteCheckpointer")

        record = self.checkpointer.get_latest_checkpoint_record(thread_id)
        if not record:
            raise ValueError(f"No checkpoint found for thread '{thread_id}'")

        state_data = json.loads(record["state_json"])
        state = GraphState(**state_data)

        if state.status != "SUSPENDED":
            raise ValueError(
                f"Thread '{thread_id}' is not in SUSPENDED state (current status: '{state.status}')"
            )

        norm_decision = decision.strip().lower()

        if norm_decision in ("approve", "approved"):
            if self.audit_ledger:
                self.audit_ledger.append_event(
                    session_id=thread_id,
                    event_type="APPROVAL_GRANTED",
                    actor_role=actor_role,
                    payload={"thread_id": thread_id, "notes": notes, "decision": "approve"},
                )

            updated_values = dict(state.values)
            updated_values["approval"] = {
                "status": "approved",
                "decision": decision,
                "notes": notes,
                "actor_role": actor_role,
            }
            resumed_state = state.copy_and_update(
                status="RUNNING",
                pending_approval=None,
                values=updated_values,
            )

            # Determine next node to resume from
            if resume_node:
                target_node = resume_node
            else:
                suspended_node = record["node_name"]
                if suspended_node in self.compiled.conditional_edges:
                    router_fn, path_map = self.compiled.conditional_edges[suspended_node]
                    branch_key = router_fn(resumed_state)
                    target_node = path_map.get(branch_key, END)
                elif suspended_node in self.compiled.edges:
                    target_node = self.compiled.edges[suspended_node]
                else:
                    target_node = END

            if target_node == END:
                resumed_state = resumed_state.copy_and_update(status="COMPLETED")
                self.checkpointer.save_checkpoint(thread_id, END, resumed_state)
                return resumed_state

            return self.compiled.invoke(resumed_state, start_node=target_node)

        elif norm_decision in ("reject", "rejected"):
            if self.audit_ledger:
                self.audit_ledger.append_event(
                    session_id=thread_id,
                    event_type="APPROVAL_REJECTED",
                    actor_role=actor_role,
                    payload={"thread_id": thread_id, "notes": notes, "decision": "reject"},
                )

            updated_values = dict(state.values)
            updated_values["approval"] = {
                "status": "rejected",
                "decision": decision,
                "notes": notes,
                "actor_role": actor_role,
            }
            rejected_state = state.copy_and_update(
                status="FAILED",
                last_error=f"Workflow execution rejected by {actor_role}: {notes or 'No notes provided'}",
                pending_approval=None,
                values=updated_values,
            )
            self.checkpointer.save_checkpoint(thread_id, record["node_name"], rejected_state)
            return rejected_state

        else:
            raise ValueError(
                f"Invalid decision '{decision}'. Must be 'approve' or 'reject'."
            )
