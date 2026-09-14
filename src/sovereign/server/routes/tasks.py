"""
src/sovereign/server/routes/tasks.py
Task management REST endpoints: submit, list, status, resume, artifacts.
"""
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sovereign.server.auth.rbac import require_role
from sovereign.tools.schemas import UserRole

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ── Request/Response Models ──────────────────────────────────────────────────


class TaskSubmitRequest(BaseModel):
    """Request body for submitting a new task."""
    prompt: str = Field(..., description="Task instruction or prompt")
    files: Optional[List[str]] = Field(
        default_factory=list, description="List of file paths to process"
    )
    model_override: Optional[str] = Field(
        default=None, description="Optional model ID override"
    )


class TaskResumeRequest(BaseModel):
    """Request body for resuming a suspended HITL workflow."""
    decision: str = Field(
        ..., pattern="^(approve|reject)$", description="Approval decision"
    )
    notes: Optional[str] = Field(
        default=None, description="Operator review notes"
    )


class TaskResponse(BaseModel):
    """Response for task creation."""
    task_id: str
    thread_id: str
    status: str


class TaskStatusResponse(BaseModel):
    """Response for task status query."""
    task_id: str
    status: str
    steps: List[Dict] = Field(default_factory=list)
    pending_approval: Optional[Dict] = None


# ── In-memory task store (wired to runtime in production) ────────────────────

_task_store: Dict[str, Dict] = {}


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=TaskResponse,
    dependencies=[Depends(require_role(UserRole.ENGINEER))],
)
async def submit_task(request: TaskSubmitRequest):
    """Submit a new task for agent execution. Requires Engineer clearance."""
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    thread_id = f"wf-{uuid.uuid4().hex[:6]}"

    _task_store[task_id] = {
        "task_id": task_id,
        "thread_id": thread_id,
        "status": "QUEUED",
        "prompt": request.prompt,
        "files": request.files or [],
        "model_override": request.model_override,
        "steps": [],
        "pending_approval": None,
    }

    return TaskResponse(task_id=task_id, thread_id=thread_id, status="QUEUED")


@router.get(
    "",
    dependencies=[Depends(require_role(UserRole.AUDITOR))],
)
async def list_tasks():
    """List active and historical tasks. Requires Auditor clearance."""
    return {
        "tasks": [
            {"task_id": t["task_id"], "status": t["status"]}
            for t in _task_store.values()
        ]
    }


@router.get(
    "/{task_id}",
    response_model=TaskStatusResponse,
    dependencies=[Depends(require_role(UserRole.AUDITOR))],
)
async def get_task_status(task_id: str):
    """Get detailed task status. Requires Auditor clearance."""
    task = _task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return TaskStatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        steps=task.get("steps", []),
        pending_approval=task.get("pending_approval"),
    )


@router.post(
    "/{task_id}/resume",
    dependencies=[Depends(require_role(UserRole.ENGINEER))],
)
async def resume_task(task_id: str, request: TaskResumeRequest):
    """Resume a suspended HITL workflow. Requires Engineer clearance."""
    task = _task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    task["status"] = "RESUMED" if request.decision == "approve" else "REJECTED"
    return {
        "task_id": task_id,
        "decision": request.decision,
        "status": task["status"],
    }


@router.get(
    "/{task_id}/artifacts/{filename}",
    dependencies=[Depends(require_role(UserRole.AUDITOR))],
)
async def get_artifact(task_id: str, filename: str):
    """Download a task output artifact. Requires Auditor clearance."""
    # Path traversal guard
    safe_name = Path(filename).name
    if safe_name != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    task = _task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    return {
        "task_id": task_id,
        "filename": safe_name,
        "status": "artifact_metadata",
    }
