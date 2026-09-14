"""
src/sovereign/sdk/__init__.py
Lightweight pure-Python SDK for the Sovereign AI Workbench.
Zero required external pip dependencies.
"""
from sovereign.tools.schemas import UserRole
from sovereign.sdk.client import SovereignClient
from sovereign.sdk.exceptions import (
    ConnectionError,
    RBACPermissionError,
    SovereignAPIError,
    SovereignConnectionError,
    SovereignError,
)
from sovereign.sdk.models import (
    AuditVerificationResult,
    NetworkTelemetryResult,
    TaskResult,
    TaskStatus,
    VRAMStatus,
)

__all__ = [
    "SovereignClient",
    "UserRole",
    "SovereignError",
    "SovereignAPIError",
    "RBACPermissionError",
    "SovereignConnectionError",
    "ConnectionError",
    "TaskStatus",
    "TaskResult",
    "VRAMStatus",
    "AuditVerificationResult",
    "NetworkTelemetryResult",
]
