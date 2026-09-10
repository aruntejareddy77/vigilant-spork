"""
src/sovereign/network/models.py
Pydantic schemas for the Network Isolation & Observability Subsystem.
"""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class NetworkEvent(BaseModel):
    """Represents an observed network socket connection event with policy evaluation verdict."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    timestamp_iso: str = Field(description="ISO 8601 UTC timestamp string")
    protocol: str = Field(default="tcp", description="Transport layer protocol: tcp, udp, etc.")
    local_address: str = Field(description="Local IP:port or path")
    remote_address: str = Field(default="", description="Remote IP:port or empty if listening")
    pid: Optional[int] = Field(default=None, description="Operating system process ID")
    process_name: str = Field(default="unknown", description="Binary or executable name")
    verdict: str = Field(description="Outcome: ALLOW or DENY")
    reason: str = Field(description="Policy explanation for the verdict")


class TelemetrySnapshot(BaseModel):
    """Aggregate snapshot of in-memory telemetry ring buffer."""
    model_config = ConfigDict(extra="forbid")

    total_events: int
    allowed_count: int
    denied_count: int
    capacity: int
    recent_events: List[NetworkEvent]


class ProbeResult(BaseModel):
    """Represents the outcome of a synthetic egress probe."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol: str
    target_host: str
    target_port: int
    outcome: str = Field(description="BLOCKED (secure) or LEAKED (insecure)")
    reason: str
    latency_ms: float


class PolicyConfig(BaseModel):
    """Schema for declarative network policy specification."""
    model_config = ConfigDict(extra="ignore")

    policy_name: str = "sovereign_default_deny"
    version: str = "1.0.0"
    allowed_loopback: List[str] = Field(default_factory=lambda: ["127.0.0.0/8", "::1/128"])
    allowed_intranet_cidrs: List[str] = Field(default_factory=list)
    denied_ports: List[int] = Field(default_factory=lambda: [53])
    default_action: str = "DENY"
