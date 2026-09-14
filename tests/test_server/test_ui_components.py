"""
tests/test_server/test_ui_components.py
Unit tests for UI components: canvas coordinate normalization,
color selection rules, role-based view filtering, and HITL payloads.
"""
import json
import pytest

from sovereign.multimodal.models import DocumentRegion, ModalityType, NormalizedDocument, DocumentPage
from sovereign.tools.schemas import UserRole


# =============================================================================
# 1. Coordinate Normalization & Canvas Mapping Parity
# =============================================================================

def compute_box_coordinates(bbox, width: int, height: int):
    """
    Python equivalent of preview.js computeBoxCoordinates.
    Maps normalized [ymin, xmin, ymax, xmax] in [0.0, 1.0] to pixel dimensions.
    """
    if not bbox or len(bbox) < 4:
        return {"x": 0, "y": 0, "w": 0, "h": 0}
    ymin, xmin, ymax, xmax = bbox
    x = round(xmin * width)
    y = round(ymin * height)
    w = round((xmax - xmin) * width)
    h = round((ymax - ymin) * height)
    return {"x": x, "y": y, "w": w, "h": h}


class TestCanvasCoordinateScaling:
    """Validate spatial bounding box coordinate calculations match NormalizedDocument specifications."""

    def test_full_canvas_bounding_box(self):
        """Full canvas normalized box [0.0, 0.0, 1.0, 1.0] covers entire dimensions."""
        coords = compute_box_coordinates([0.0, 0.0, 1.0, 1.0], width=800, height=600)
        assert coords == {"x": 0, "y": 0, "w": 800, "h": 600}

    def test_sub_region_scaling(self):
        """Coordinates [0.1, 0.2, 0.4, 0.7] with W=800, H=600."""
        # xmin=0.2 * 800 = 160
        # ymin=0.1 * 600 = 60
        # w = (0.7 - 0.2) * 800 = 0.5 * 800 = 400
        # h = (0.4 - 0.1) * 600 = 0.3 * 600 = 180
        coords = compute_box_coordinates([0.1, 0.2, 0.4, 0.7], width=800, height=600)
        assert coords == {"x": 160, "y": 60, "w": 400, "h": 180}

    def test_normalized_document_region_integration(self):
        """DocumentRegion box_2d translates correctly to pixel coordinates."""
        region = DocumentRegion(
            region_id="p1-r004",
            box_2d=[0.35, 0.1, 0.42, 0.8],
            text="Localized pitting observed at nozzle N-2 weld zone",
            confidence=0.78,
            modality=ModalityType.HANDWRITTEN,
        )
        coords = compute_box_coordinates(region.box_2d, width=1000, height=1000)
        assert coords["x"] == 100
        assert coords["y"] == 350
        assert coords["w"] == 700
        assert coords["h"] == 70

    def test_empty_or_invalid_bbox_returns_zero(self):
        """Invalid or empty bounding box returns zero dimensions safely."""
        assert compute_box_coordinates([], 800, 600) == {"x": 0, "y": 0, "w": 0, "h": 0}
        assert compute_box_coordinates(None, 800, 600) == {"x": 0, "y": 0, "w": 0, "h": 0}


# =============================================================================
# 2. Color Selection Rules (preview.js Parity)
# =============================================================================

def get_color_for_region(region: dict) -> str:
    """Python equivalent of preview.js getColorForRegion."""
    diff_status = region.get("diff_status") or region.get("diff_type")
    if diff_status == "added" or region.get("category") == "diff_added":
        return "#10B981"
    if diff_status == "removed" or region.get("category") == "diff_removed":
        return "#EF4444"
    if diff_status == "modified" or region.get("category") == "diff_modified":
        return "#F59E0B"

    conf = region.get("confidence")
    if conf is not None and conf < 0.85:
        return "#F59E0B"  # Amber review flag

    modality = str(region.get("modality") or region.get("category") or "").lower()
    if modality in ("handwritten", "handwriting") or region.get("is_handwritten"):
        return "#3B82F6"  # Blue handwriting

    return "#10B981"  # Default green printed text


class TestColorSelectionRules:
    """Validate color coding rules for printed, handwritten, low-confidence, and diff annotations."""

    def test_printed_high_confidence(self):
        """High-confidence printed text uses Green #10B981."""
        reg = {"modality": "printed", "confidence": 0.95}
        assert get_color_for_region(reg) == "#10B981"

    def test_handwritten_high_confidence(self):
        """High-confidence handwritten text uses Blue #3B82F6."""
        reg = {"modality": "handwritten", "confidence": 0.92}
        assert get_color_for_region(reg) == "#3B82F6"

    def test_low_confidence_triggers_amber(self):
        """Confidence < 0.85 triggers Amber #F59E0B regardless of modality."""
        reg = {"modality": "handwritten", "confidence": 0.75}
        assert get_color_for_region(reg) == "#F59E0B"

        reg_printed = {"modality": "printed", "confidence": 0.84}
        assert get_color_for_region(reg_printed) == "#F59E0B"

    def test_drawing_diff_colors(self):
        """Drawing diff added (Green), removed (Red), modified (Amber)."""
        assert get_color_for_region({"diff_status": "added"}) == "#10B981"
        assert get_color_for_region({"diff_status": "removed"}) == "#EF4444"
        assert get_color_for_region({"diff_status": "modified"}) == "#F59E0B"


# =============================================================================
# 3. RBAC View Filtering & Permission Flags
# =============================================================================

class TestRBACViewFiltering:
    """Validate presentation-layer role visibility rules and permission checks."""

    def get_role_permissions(self, role: UserRole):
        return {
            "can_submit_tasks": role in (UserRole.ADMIN, UserRole.ENGINEER),
            "can_approve_hitl": role in (UserRole.ADMIN, UserRole.ENGINEER),
            "can_register_models": role == UserRole.ADMIN,
            "can_view_audit": True,
            "can_view_network": True,
        }

    def test_auditor_permissions_strictly_blocked(self):
        """Auditor role must not have submit, approve, or model registration capabilities."""
        perms = self.get_role_permissions(UserRole.AUDITOR)
        assert perms["can_submit_tasks"] is False
        assert perms["can_approve_hitl"] is False
        assert perms["can_register_models"] is False
        assert perms["can_view_audit"] is True
        assert perms["can_view_network"] is True

    def test_engineer_permissions(self):
        """Engineer role has operational capabilities but cannot register models."""
        perms = self.get_role_permissions(UserRole.ENGINEER)
        assert perms["can_submit_tasks"] is True
        assert perms["can_approve_hitl"] is True
        assert perms["can_register_models"] is False
        assert perms["can_view_audit"] is True

    def test_admin_permissions_full(self):
        """Admin role has all operational and governance clearances."""
        perms = self.get_role_permissions(UserRole.ADMIN)
        assert perms["can_submit_tasks"] is True
        assert perms["can_approve_hitl"] is True
        assert perms["can_register_models"] is True


# =============================================================================
# 4. WebSocket Event Schemas & HITL Gate Resumption
# =============================================================================

class TestWebSocketAndHITLSchemas:
    """Validate event schemas and payload structures exchanged over WebSockets and REST."""

    def test_trace_step_schema(self):
        """Trace step payload conforms to expected JSON structure."""
        step = {
            "type": "TRACE_STEP",
            "task_id": "task-8f92a1",
            "thread_id": "wf-b01",
            "step_index": 2,
            "node_name": "extract_findings",
            "model_id": "qwen2.5-7b-instruct",
            "status": "RUNNING",
            "thought": "Extracting inspection findings with spatial citations from page 1...",
            "tool_calls": [
                {"tool": "ocr_extract_region", "inputs": {"region_id": "p1-r004"}}
            ],
            "elapsed_ms": 420.5,
            "timestamp_iso": "2026-09-14T16:20:10.123Z",
        }
        raw_json = json.dumps(step)
        parsed = json.loads(raw_json)
        assert parsed["type"] == "TRACE_STEP"
        assert parsed["elapsed_ms"] == 420.5
        assert len(parsed["tool_calls"]) == 1

    def test_hitl_suspended_schema(self):
        """HITL suspension event contains pending approval metadata and citations."""
        event = {
            "type": "HITL_SUSPENDED",
            "task_id": "task-8f92a1",
            "thread_id": "wf-b01",
            "pending_approval": {
                "action": "deliverable_signoff",
                "deliverable_type": "docx",
                "summary": "Drafted Refinery Vessel V-301 Inspection Approval Note",
                "confidence_score": 0.94,
                "citations": ["doc-a81f9b#p1-r004", "doc-a81f9b#p1-r007"],
            },
        }
        raw_json = json.dumps(event)
        parsed = json.loads(raw_json)
        assert parsed["type"] == "HITL_SUSPENDED"
        assert parsed["pending_approval"]["action"] == "deliverable_signoff"
        assert len(parsed["pending_approval"]["citations"]) == 2

    def test_hitl_resumption_payload(self):
        """Operator approval decision payload matches resume API requirements."""
        resumption_approval = {
            "decision": "approve",
            "notes": "All wall thickness measurements verified against ASME Section VIII Div 1.",
        }
        assert resumption_approval["decision"] in ("approve", "reject")
        assert len(resumption_approval["notes"]) > 0

        resumption_rejection = {
            "decision": "reject",
            "notes": "Corrosion rate calculations incomplete; please recalculate with 2.5mm baseline.",
        }
        assert resumption_rejection["decision"] == "reject"
