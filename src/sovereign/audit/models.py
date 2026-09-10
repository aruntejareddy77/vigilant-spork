"""
src/sovereign/audit/models.py
Pydantic schemas for the Cryptographic Audit Subsystem.
"""
from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class AuditEvent(BaseModel):
    """
    Represents a verified cryptographic audit event record in the Sovereign Workbench.
    All fields conform to RFC 8785 canonical JSON schema specifications.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    seq_num: int = Field(ge=0, description="Monotonically increasing integer sequence number starting at 0")
    timestamp_iso: str = Field(description="ISO 8601 UTC timestamp string (e.g. 2026-09-10T10:00:00Z)")
    session_id: str = Field(min_length=1, description="Unique session identifier for session slice extraction")
    event_type: str = Field(min_length=1, description="Categorical event type (e.g. tool_execution, model_invocation, security_alert)")
    actor_role: str = Field(min_length=1, description="Role of the actor triggering the event (e.g. system, user, compliance_officer)")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary structured event payload details")
    previous_hash: str = Field(min_length=64, max_length=64, description="Hex-encoded SHA-256 hash of previous record or 64 zeros for genesis")
    entry_hash: str = Field(min_length=64, max_length=64, description="Hex-encoded SHA-256 hash over the canonical representation of this record")
