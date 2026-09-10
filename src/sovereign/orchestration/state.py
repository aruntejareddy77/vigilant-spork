"""
src/sovereign/orchestration/state.py
Deterministic state schema for Sovereign AI Workbench agentic workflows.
"""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


GraphStatus = Literal["RUNNING", "SUSPENDED", "COMPLETED", "FAILED"]


class GraphState(BaseModel):
    """
    Session and execution state for a deterministic StateGraph workflow.
    Ensures safe persistence, step count tracking, and retry bounding.
    """
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    thread_id: str
    step_count: int = 0
    max_steps: int = 25
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    intermediate_steps: List[Dict[str, Any]] = Field(default_factory=list)
    tool_outputs: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    status: GraphStatus = "RUNNING"
    pending_approval: Optional[Dict[str, Any]] = None
    values: Dict[str, Any] = Field(default_factory=dict)

    def copy_and_update(self, **updates: Any) -> "GraphState":
        """
        Produce a new state instance with updated fields.
        Values dict updates are merged shallowly unless explicitly overwritten.
        """
        current_data = self.model_dump()
        if "values" in updates and isinstance(updates["values"], dict):
            merged_values = dict(current_data.get("values", {}))
            merged_values.update(updates["values"])
            updates["values"] = merged_values
        
        current_data.update(updates)
        return GraphState(**current_data)
