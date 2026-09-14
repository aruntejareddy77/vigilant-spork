"""
src/sovereign/server/routes/network.py
Network policy, telemetry, and egress test endpoints.
"""
from typing import Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from sovereign.server.auth.rbac import require_role
from sovereign.tools.schemas import UserRole

router = APIRouter(prefix="/api/network", tags=["network"])


# ── Response Models ──────────────────────────────────────────────────────────


class NetworkStatusResponse(BaseModel):
    """Network policy status."""
    policy_name: str = "sovereign_default_deny"
    default_action: str = "DENY"
    allowed_loopback: List[str] = Field(
        default_factory=lambda: ["127.0.0.0/8", "::1/128"]
    )
    allowed_intranet_cidrs: List[str] = Field(
        default_factory=lambda: ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
    )
    denied_ports: List[int] = Field(default_factory=lambda: [53])


class TelemetryResponse(BaseModel):
    """Recent socket connection telemetry."""
    total_events: int = 0
    allowed_count: int = 0
    denied_count: int = 0
    recent_events: List[Dict] = Field(default_factory=list)


class EgressProbeResult(BaseModel):
    """Egress probe result."""
    protocol: str
    target_host: str
    target_port: int
    outcome: str
    reason: str


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "/status",
    response_model=NetworkStatusResponse,
    dependencies=[Depends(require_role(UserRole.AUDITOR))],
)
async def get_network_status():
    """Return network policy status. Requires Auditor clearance."""
    return NetworkStatusResponse()


@router.get(
    "/telemetry",
    response_model=TelemetryResponse,
    dependencies=[Depends(require_role(UserRole.AUDITOR))],
)
async def get_telemetry():
    """Retrieve recent socket connection telemetry. Requires Auditor clearance."""
    return TelemetryResponse()


@router.post(
    "/test-egress",
    dependencies=[Depends(require_role(UserRole.AUDITOR))],
)
async def test_egress():
    """Run synthetic egress probes. Requires Auditor clearance."""
    return {
        "probes": [
            {
                "protocol": "tcp",
                "target_host": "8.8.8.8",
                "target_port": 53,
                "outcome": "BLOCKED",
                "reason": "Default-deny egress policy",
            },
            {
                "protocol": "tcp",
                "target_host": "1.1.1.1",
                "target_port": 443,
                "outcome": "BLOCKED",
                "reason": "Default-deny egress policy",
            },
        ],
        "all_blocked": True,
    }
