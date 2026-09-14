"""
src/sovereign/server/routes/demos.py
Guided demonstration workflow launch endpoints.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException

from sovereign.server.auth.rbac import require_role
from sovereign.tools.schemas import UserRole

router = APIRouter(prefix="/api/demos", tags=["demos"])

VALID_DEMOS = {"demo_a", "demo_b", "demo_c"}


@router.post(
    "/{demo_id}/launch",
    dependencies=[Depends(require_role(UserRole.ENGINEER))],
)
async def launch_demo(demo_id: str):
    """
    Launch a pre-configured demonstration workflow.
    Requires Engineer clearance.

    Valid demo_id values: demo_a, demo_b, demo_c
    """
    if demo_id not in VALID_DEMOS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown demo '{demo_id}'. Valid demos: {', '.join(sorted(VALID_DEMOS))}",
        )

    task_id = f"demo-{demo_id}-{uuid.uuid4().hex[:6]}"
    thread_id = f"wf-{uuid.uuid4().hex[:6]}"

    return {
        "demo_id": demo_id,
        "task_id": task_id,
        "thread_id": thread_id,
        "status": "LAUNCHED",
    }
