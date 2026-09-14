"""
src/sovereign/server/routes/demos.py
Guided demonstration workflow launch endpoints for core SIH operational modes:
- Demo A: Scanned Inspection Report -> OCR -> Findings Extraction -> HITL Gate -> Word (.docx) Export
- Demo B: Industrial CSV Parsing -> NumPy/SciPy Code Gen -> Isolated Sandbox Execution -> Auto-Fix Retry -> Verified Script & Logs
- Demo C: P&ID Drawing Revision Comparison -> Diff Detection -> Visual Overlay -> Change Register
"""
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sovereign.server.auth.rbac import require_role
from sovereign.server.routes.tasks import _task_store
from sovereign.tools.schemas import UserRole

router = APIRouter(prefix="/api/demos", tags=["demos"])

VALID_DEMOS = {"demo_a", "demo_b", "demo_c"}

DEMO_CONFIGS = {
    "demo_a": {
        "title": "Demo A: Inspection Report -> Approval Note (DEMO-01)",
        "description": "Scanned inspection report OCR extraction, spatial citations, HITL approval gate, and Word memo export.",
        "steps": [
            "1. Ingest Inspection Report",
            "2. OCR & Findings Extraction",
            "3. Human-in-the-Loop Sign-Off",
            "4. Export Verified Memo (.docx)"
        ]
    },
    "demo_b": {
        "title": "Demo B: Industrial Code Gen & Sandbox Execution (DEMO-02)",
        "description": "Historian CSV data ingestion, Python code generation, isolated CodeSandbox execution, auto-fix retry loop, verified script deliverable.",
        "steps": [
            "1. Ingest Historian CSV Data",
            "2. Generate Vibration Analysis Code",
            "3. Execute Isolated CodeSandbox",
            "4. Bounded Auto-Fix Retry Loop",
            "5. Deliver Verified Script & Logs"
        ]
    },
    "demo_c": {
        "title": "Demo C: P&ID Drawing Revision Diff (DEMO-03)",
        "description": "Multi-revision drawing alignment, visual diff detection (added/modified/removed), canvas overlay, change register export.",
        "steps": [
            "1. Align Revision A & Revision B",
            "2. Multi-Layer Diff Detection",
            "3. Render Color-Coded Overlay",
            "4. Export Revision Change Table"
        ]
    }
}


@router.get(
    "",
    dependencies=[Depends(require_role(UserRole.AUDITOR))],
)
async def list_demos():
    """List available guided SIH demonstration workflows. Requires Auditor clearance."""
    return {
        "demos": [
            {"demo_id": d_id, **d_cfg}
            for d_id, d_cfg in DEMO_CONFIGS.items()
        ]
    }


@router.get(
    "/{demo_id}",
    dependencies=[Depends(require_role(UserRole.AUDITOR))],
)
async def get_demo(demo_id: str):
    """Get metadata for a specific demonstration workflow. Requires Auditor clearance."""
    if demo_id not in VALID_DEMOS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown demo '{demo_id}'. Valid demos: {', '.join(sorted(VALID_DEMOS))}",
        )
    return {"demo_id": demo_id, **DEMO_CONFIGS[demo_id]}


@router.post(
    "/{demo_id}/launch",
    dependencies=[Depends(require_role(UserRole.ENGINEER))],
)
async def launch_demo(demo_id: str):
    """
    Launch a pre-configured demonstration workflow.
    Requires Engineer clearance (FR-UI-5).
    Auditor clearance receives HTTP 403 Forbidden.

    Valid demo_id values: demo_a, demo_b, demo_c
    """
    if demo_id not in VALID_DEMOS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown demo '{demo_id}'. Valid demos: {', '.join(sorted(VALID_DEMOS))}",
        )

    task_id = f"demo-{demo_id}-{uuid.uuid4().hex[:6]}"
    thread_id = f"wf-{uuid.uuid4().hex[:6]}"

    if demo_id == "demo_a":
        # Demo A: Inspection Report -> OCR -> Findings Extraction -> HITL Gate -> Word (.docx)
        task_data = {
            "task_id": task_id,
            "thread_id": thread_id,
            "demo_id": "demo_a",
            "status": "SUSPENDED",
            "prompt": "Extract shell thickness findings from refinery_vessel_inspection_v301.png and draft approval memo.",
            "files": ["refinery_vessel_inspection_v301.png"],
            "steps": [
                {
                    "type": "TRACE_STEP",
                    "step_index": 1,
                    "node_name": "ingest_report",
                    "model_id": "system",
                    "status": "COMPLETED",
                    "thought": "Ingested high-resolution scan: refinery_vessel_inspection_v301.png (2480x3508)",
                    "elapsed_ms": 115.0,
                },
                {
                    "type": "TRACE_STEP",
                    "step_index": 2,
                    "node_name": "ocr_findings_extraction",
                    "model_id": "qwen2.5-7b-instruct",
                    "status": "COMPLETED",
                    "thought": "OCR extracted 4 bounding regions. Finding: localized pitting at nozzle N-2 (doc-v301#p1-r004, confidence 0.78 < 0.85).",
                    "tool_calls": [
                        {"tool": "ocr_extract_region", "inputs": {"region_id": "p1-r004", "box": [0.35, 0.1, 0.42, 0.8]}}
                    ],
                    "elapsed_ms": 345.0,
                },
                {
                    "type": "TRACE_STEP",
                    "step_index": 3,
                    "node_name": "hitl_review_gate",
                    "model_id": "system",
                    "status": "SUSPENDED",
                    "thought": "Synthesized findings. Pausing execution at HITL approval gate for operator verification.",
                    "elapsed_ms": 12.0,
                },
            ],
            "pending_approval": {
                "action": "deliverable_signoff",
                "deliverable_type": "docx",
                "summary": "Refinery Vessel V-301 Inspection Approval Note",
                "confidence_score": 0.94,
                "citations": ["doc-v301#p1-r004"],
            },
            "artifacts": [],
        }

    elif demo_id == "demo_b":
        # Demo B: Industrial Code Gen & Isolated Sandbox Execution with Auto-Fix Loop
        task_data = {
            "task_id": task_id,
            "thread_id": thread_id,
            "demo_id": "demo_b",
            "status": "COMPLETED",
            "prompt": "Parse sensor historian CSV data and compute peak vibration frequencies with automated test coverage.",
            "files": ["historian_vibration_sample.csv"],
            "steps": [
                {
                    "type": "TRACE_STEP",
                    "step_index": 1,
                    "node_name": "parse_historian_csv",
                    "model_id": "system",
                    "status": "COMPLETED",
                    "thought": "Ingested 10,000 historian rows. Identified timestamp and vibration sensor telemetry columns.",
                    "elapsed_ms": 82.0,
                },
                {
                    "type": "TRACE_STEP",
                    "step_index": 2,
                    "node_name": "code_generation",
                    "model_id": "deepseek-coder-6.7b",
                    "status": "COMPLETED",
                    "thought": "Generated Python FFT spectral peak analysis script using NumPy and SciPy.",
                    "elapsed_ms": 470.0,
                },
                {
                    "type": "TRACE_STEP",
                    "step_index": 3,
                    "node_name": "sandbox_execution",
                    "model_id": "system",
                    "status": "ERROR",
                    "thought": "CodeSandbox execution failed: KeyError 'vibration_rms' (unmapped column name in CSV header).",
                    "elapsed_ms": 210.0,
                },
                {
                    "type": "TRACE_STEP",
                    "step_index": 4,
                    "node_name": "auto_fix_retry",
                    "model_id": "deepseek-coder-6.7b",
                    "status": "COMPLETED",
                    "thought": "Auto-fix iteration 1: Remapped column to 'vib_rms_g' and re-executed CodeSandbox. All unit tests passed.",
                    "elapsed_ms": 320.0,
                },
                {
                    "type": "TRACE_STEP",
                    "step_index": 5,
                    "node_name": "verified_script",
                    "model_id": "system",
                    "status": "COMPLETED",
                    "thought": "Exported verified vibration_analysis.py and execution.log to local output repository.",
                    "elapsed_ms": 35.0,
                    "artifact_url": f"/api/tasks/{task_id}/artifacts/vibration_analysis.py",
                    "artifact_name": "vibration_analysis.py",
                },
            ],
            "pending_approval": None,
            "artifacts": ["vibration_analysis.py", "execution.log"],
        }

    else:
        # Demo C: P&ID Drawing Revision Comparison & Overlay
        task_data = {
            "task_id": task_id,
            "thread_id": thread_id,
            "demo_id": "demo_c",
            "status": "COMPLETED",
            "prompt": "Compare P&ID drawing Revision A and Revision B; detect added/removed/modified components and export change table.",
            "files": ["pid_drawing_rev_a.png", "pid_drawing_rev_b.png"],
            "steps": [
                {
                    "type": "TRACE_STEP",
                    "step_index": 1,
                    "node_name": "align_revisions",
                    "model_id": "system",
                    "status": "COMPLETED",
                    "thought": "Homography alignment completed: Rev A and Rev B coordinate planes matched with 99.4% structural similarity.",
                    "elapsed_ms": 140.0,
                },
                {
                    "type": "TRACE_STEP",
                    "step_index": 2,
                    "node_name": "diff_detection",
                    "model_id": "system",
                    "status": "COMPLETED",
                    "thought": "Detected 3 visual changes across revisions: 1 added valve, 1 modified pipe size, 1 decommissioned cock.",
                    "elapsed_ms": 390.0,
                },
                {
                    "type": "TRACE_STEP",
                    "step_index": 3,
                    "node_name": "visual_overlay",
                    "model_id": "system",
                    "status": "COMPLETED",
                    "thought": "Rendered multi-colored visual diff overlay (Green=Added, Red=Removed, Amber=Modified).",
                    "elapsed_ms": 85.0,
                },
                {
                    "type": "TRACE_STEP",
                    "step_index": 4,
                    "node_name": "change_register",
                    "model_id": "system",
                    "status": "COMPLETED",
                    "thought": "Compiled structured revision change register into pid_revision_change_register.csv.",
                    "elapsed_ms": 50.0,
                    "artifact_url": f"/api/tasks/{task_id}/artifacts/pid_revision_change_register.csv",
                    "artifact_name": "pid_revision_change_register.csv",
                },
            ],
            "pending_approval": None,
            "diff_regions": [
                {
                    "region_id": "diff-add-01",
                    "coordinates": [0.3, 0.25, 0.42, 0.42],
                    "diff_status": "added",
                    "text": "Added bypass relief valve RV-402",
                },
                {
                    "region_id": "diff-mod-01",
                    "coordinates": [0.5, 0.6, 0.65, 0.78],
                    "diff_status": "modified",
                    "text": 'Pipe diameter upsized 3" -> 4"',
                },
                {
                    "region_id": "diff-rem-01",
                    "coordinates": [0.7, 0.15, 0.82, 0.32],
                    "diff_status": "removed",
                    "text": "Decommissioned manual sampling cock SC-101",
                },
            ],
            "artifacts": ["pid_revision_change_register.csv", "pid_diff_overlay.png"],
        }

    _task_store[task_id] = task_data

    return {
        "demo_id": demo_id,
        "task_id": task_id,
        "thread_id": thread_id,
        "status": "LAUNCHED",
        "initial_status": task_data["status"],
        "steps_count": len(task_data["steps"]),
        "pending_approval": task_data.get("pending_approval"),
        "artifacts": task_data.get("artifacts", []),
        "diff_regions": task_data.get("diff_regions", []),
    }
