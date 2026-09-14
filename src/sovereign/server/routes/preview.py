"""
src/sovereign/server/routes/preview.py
Document preview metadata and bounding box coordinate endpoints.
"""
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sovereign.server.auth.rbac import require_role
from sovereign.tools.schemas import UserRole

router = APIRouter(prefix="/api/preview", tags=["preview"])


# ── Response Models ──────────────────────────────────────────────────────────


class BoundingBox(BaseModel):
    """Normalized bounding box coordinates [ymin, xmin, ymax, xmax] in [0.0, 1.0]."""
    region_id: str
    coordinates: List[float] = Field(description="[ymin, xmin, ymax, xmax]")
    text: str = ""
    confidence: float = 0.0
    category: str = "printed"


class PreviewResponse(BaseModel):
    """Normalized document preview metadata."""
    doc_id: str
    page_count: int = 1
    page_width: int = 2480
    page_height: int = 3508
    bounding_boxes: List[BoundingBox] = Field(default_factory=list)


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "/{doc_id}",
    response_model=PreviewResponse,
    dependencies=[Depends(require_role(UserRole.AUDITOR))],
)
async def get_preview(doc_id: str):
    """Return NormalizedDocument metadata and bounding boxes. Requires Auditor clearance."""
    return PreviewResponse(
        doc_id=doc_id,
        bounding_boxes=[
            BoundingBox(
                region_id="p1-r001",
                coordinates=[0.1, 0.05, 0.15, 0.45],
                text="Sample extracted text",
                confidence=0.95,
                category="printed",
            ),
        ],
    )
