"""
src/sovereign/sdk/models.py
Typed data models and enums for the Sovereign Python SDK.
Built strictly on the Python standard library with zero external dependencies.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskStatus(str, Enum):
    """Task execution lifecycle status."""
    SUBMITTED = "SUBMITTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUSPENDED = "SUSPENDED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


@dataclass
class TaskResult:
    """Represents the response from a task submission, status poll, or resume."""
    task_id: str
    thread_id: Optional[str] = None
    status: TaskStatus = TaskStatus.SUBMITTED
    output: Optional[str] = None
    pending_approval: Optional[Dict[str, Any]] = None
    artifacts: List[str] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VRAMStatus:
    """Current GPU memory budget and allocation metrics."""
    total_mb: int
    usable_mb: int
    allocated_mb: int
    available_mb: int
    loaded_models: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AuditVerificationResult:
    """Results of a cryptographic SHA-256 ledger integrity verification."""
    is_valid: bool
    records_checked: int = 0
    tip_hash: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class NetworkTelemetryResult:
    """Single socket connection telemetry event captured by the network monitor."""
    timestamp_iso: str
    protocol: str
    local_address: str
    remote_address: Optional[str] = None
    pid: Optional[int] = None
    process_name: Optional[str] = None
    verdict: str = "BLOCKED"
    reason: Optional[str] = None
