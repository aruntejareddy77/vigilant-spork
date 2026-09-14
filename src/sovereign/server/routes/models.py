"""
src/sovereign/server/routes/models.py
Model catalog and VRAM scheduler endpoints.
"""
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from sovereign.server.auth.rbac import require_role
from sovereign.tools.schemas import UserRole

router = APIRouter(prefix="/api/models", tags=["models"])


# ── Response Models ──────────────────────────────────────────────────────────


class VRAMMetrics(BaseModel):
    """VRAM memory metrics response."""
    total_mb: int = 24576
    usable_mb: int = 22528
    allocated_mb: int = 0
    available_mb: int = 22528
    loaded_models: List[Dict] = Field(default_factory=list)


class ModelInfo(BaseModel):
    """Model catalog entry."""
    model_id: str
    engine: str
    capabilities: List[str] = Field(default_factory=list)
    status: str = "registered"


class ModelRegisterRequest(BaseModel):
    """Request body for hot-registering a model."""
    model_id: str
    engine: str = "mock"
    capabilities: List[str] = Field(default_factory=list)


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "",
    dependencies=[Depends(require_role(UserRole.AUDITOR))],
)
async def list_models():
    """List registered models. Requires Auditor clearance."""
    return {
        "models": [
            {
                "model_id": "qwen2.5-7b-instruct",
                "engine": "sglang",
                "capabilities": ["reasoning", "code"],
                "status": "registered",
            }
        ]
    }


@router.get(
    "/vram",
    response_model=VRAMMetrics,
    dependencies=[Depends(require_role(UserRole.AUDITOR))],
)
async def get_vram_metrics():
    """Return VRAM memory metrics. Requires Auditor clearance."""
    return VRAMMetrics()


@router.post(
    "/register",
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def register_model(request: ModelRegisterRequest):
    """Hot-register a new model manifest. Requires Admin clearance."""
    return {
        "model_id": request.model_id,
        "engine": request.engine,
        "status": "registered",
    }
