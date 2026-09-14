"""
tests/test_server/test_demo_workflows.py
Integration tests for guided SIH demonstration workflows:
- Demo A: Scanned Inspection Report -> Findings Extraction -> HITL Gate -> Word Export
- Demo B: Industrial Code Gen & Sandbox Execution with Auto-Fix Loop
- Demo C: P&ID Drawing Revision Diff & Overlay
- RBAC least-privilege enforcement (Auditor denied demo execution)
"""
import pytest
from fastapi.testclient import TestClient

from sovereign.server.app import create_app
from sovereign.server.auth.tokens import create_access_token
from sovereign.server.config import ServerConfig
from sovereign.tools.schemas import UserRole

SECRET = "test-secret-for-demos"


@pytest.fixture
def app():
    """Create test application."""
    config = ServerConfig(secret_key=SECRET)
    return create_app(server_config=config)


@pytest.fixture
def client(app):
    """Create TestClient bound to localhost:8000."""
    return TestClient(app, base_url="http://localhost:8000")


def _auth_header(role: UserRole):
    """Create authorization header for role."""
    token = create_access_token(role, SECRET)
    return {"Authorization": f"Bearer {token}", "host": "localhost:8000"}


class TestDemoMetadata:
    """Verify demo catalog endpoints."""

    def test_list_demos_as_auditor(self, client):
        """Auditor can inspect available demo workflows."""
        res = client.get("/api/demos", headers=_auth_header(UserRole.AUDITOR))
        assert res.status_code == 200
        data = res.json()
        assert "demos" in data
        assert len(data["demos"]) == 3
        demo_ids = [d["demo_id"] for d in data["demos"]]
        assert "demo_a" in demo_ids
        assert "demo_b" in demo_ids
        assert "demo_c" in demo_ids

    def test_get_demo_detail(self, client):
        """Get detail for Demo A."""
        res = client.get("/api/demos/demo_a", headers=_auth_header(UserRole.AUDITOR))
        assert res.status_code == 200
        data = res.json()
        assert data["demo_id"] == "demo_a"
        assert len(data["steps"]) == 4

    def test_get_invalid_demo_404(self, client):
        """Requesting nonexistent demo returns 404."""
        res = client.get("/api/demos/demo_invalid", headers=_auth_header(UserRole.AUDITOR))
        assert res.status_code == 404


class TestDemoAWorkflow:
    """Demo A: Inspection Report -> Findings Extraction -> HITL Review -> Docx Deliverable."""

    def test_demo_a_full_lifecycle(self, client):
        """
        1. Launch Demo A as Engineer -> returns task_id, status LAUNCHED, initial SUSPENDED.
        2. Inspect task status -> 3 steps, pending approval for docx signoff with citations.
        3. Resume task with approval -> transitions to COMPLETED, adds step 4, delivers docx.
        4. Query artifact metadata.
        """
        # Step 1: Launch Demo A
        launch_res = client.post("/api/demos/demo_a/launch", headers=_auth_header(UserRole.ENGINEER))
        assert launch_res.status_code == 200
        data = launch_res.json()
        assert data["demo_id"] == "demo_a"
        assert data["status"] == "LAUNCHED"
        assert data["initial_status"] == "SUSPENDED"
        task_id = data["task_id"]

        # Step 2: Check Task Status before approval
        status_res = client.get(f"/api/tasks/{task_id}", headers=_auth_header(UserRole.AUDITOR))
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["status"] == "SUSPENDED"
        assert len(status_data["steps"]) == 3
        assert status_data["pending_approval"] is not None
        assert status_data["pending_approval"]["action"] == "deliverable_signoff"
        assert "doc-v301#p1-r004" in status_data["pending_approval"]["citations"]

        # Step 3: Approve HITL Gate
        resume_res = client.post(
            f"/api/tasks/{task_id}/resume",
            json={"decision": "approve", "notes": "Vessel wall thickness verified against ASME VIII Div 1."},
            headers=_auth_header(UserRole.ENGINEER),
        )
        assert resume_res.status_code == 200
        assert resume_res.json()["status"] == "COMPLETED"

        # Step 4: Verify completed state and deliverable artifact
        final_status = client.get(f"/api/tasks/{task_id}", headers=_auth_header(UserRole.AUDITOR))
        assert final_status.status_code == 200
        final_data = final_status.json()
        assert final_data["status"] == "COMPLETED"
        assert final_data["pending_approval"] is None
        assert len(final_data["steps"]) == 4
        assert "Refinery_Inspection_Approval_Note.docx" in final_data["artifacts"]

        # Step 5: Verify artifact download endpoint
        artifact_res = client.get(
            f"/api/tasks/{task_id}/artifacts/Refinery_Inspection_Approval_Note.docx",
            headers=_auth_header(UserRole.AUDITOR),
        )
        assert artifact_res.status_code == 200
        assert artifact_res.json()["filename"] == "Refinery_Inspection_Approval_Note.docx"


class TestDemoBWorkflow:
    """Demo B: Industrial Code Gen & Isolated Sandbox Execution with Auto-Fix Loop."""

    def test_demo_b_full_lifecycle(self, client):
        """
        1. Launch Demo B as Engineer -> returns task_id, status LAUNCHED, initial COMPLETED.
        2. Inspect task status -> 5 steps including error and auto-fix retry step.
        3. Verify verified script and execution log deliverables.
        """
        launch_res = client.post("/api/demos/demo_b/launch", headers=_auth_header(UserRole.ENGINEER))
        assert launch_res.status_code == 200
        data = launch_res.json()
        assert data["demo_id"] == "demo_b"
        assert data["status"] == "LAUNCHED"
        assert data["initial_status"] == "COMPLETED"
        assert "vibration_analysis.py" in data["artifacts"]
        task_id = data["task_id"]

        status_res = client.get(f"/api/tasks/{task_id}", headers=_auth_header(UserRole.AUDITOR))
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["status"] == "COMPLETED"
        assert len(status_data["steps"]) == 5

        # Verify auto-fix loop steps
        step_nodes = [s["node_name"] for s in status_data["steps"]]
        assert "code_generation" in step_nodes
        assert "sandbox_execution" in step_nodes
        assert "auto_fix_retry" in step_nodes
        assert "verified_script" in step_nodes

        # Verify code artifact download
        art_res = client.get(
            f"/api/tasks/{task_id}/artifacts/vibration_analysis.py",
            headers=_auth_header(UserRole.AUDITOR),
        )
        assert art_res.status_code == 200
        assert art_res.json()["filename"] == "vibration_analysis.py"


class TestDemoCWorkflow:
    """Demo C: P&ID Drawing Revision Comparison & Overlay."""

    def test_demo_c_full_lifecycle(self, client):
        """
        1. Launch Demo C as Engineer -> returns task_id, diff regions, artifacts.
        2. Inspect task status -> 4 steps including alignment, diff detection, overlay, change register.
        3. Verify diff bounding boxes contain added, modified, removed callouts.
        4. Verify change register deliverable.
        """
        launch_res = client.post("/api/demos/demo_c/launch", headers=_auth_header(UserRole.ENGINEER))
        assert launch_res.status_code == 200
        data = launch_res.json()
        assert data["demo_id"] == "demo_c"
        assert data["status"] == "LAUNCHED"
        assert len(data["diff_regions"]) == 3
        task_id = data["task_id"]

        # Verify diff statuses
        diff_statuses = {r["diff_status"] for r in data["diff_regions"]}
        assert diff_statuses == {"added", "modified", "removed"}

        # Inspect task status
        status_res = client.get(f"/api/tasks/{task_id}", headers=_auth_header(UserRole.AUDITOR))
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["status"] == "COMPLETED"
        assert len(status_data["steps"]) == 4

        # Verify change register artifact
        art_res = client.get(
            f"/api/tasks/{task_id}/artifacts/pid_revision_change_register.csv",
            headers=_auth_header(UserRole.AUDITOR),
        )
        assert art_res.status_code == 200
        assert art_res.json()["filename"] == "pid_revision_change_register.csv"


class TestDemoRBACEnforcement:
    """Validate that Auditor role is strictly prohibited from executing demo workflows."""

    def test_auditor_denied_demo_launch(self, client):
        """Auditor receives 403 Forbidden when trying to launch Demo A, B, or C."""
        for demo_id in ("demo_a", "demo_b", "demo_c"):
            res = client.post(f"/api/demos/{demo_id}/launch", headers=_auth_header(UserRole.AUDITOR))
            assert res.status_code == 403, f"Auditor was not blocked from launching {demo_id}"

    def test_auditor_denied_demo_resume(self, client):
        """Auditor cannot approve or resume suspended demo task."""
        # Launch as Engineer
        launch_res = client.post("/api/demos/demo_a/launch", headers=_auth_header(UserRole.ENGINEER))
        task_id = launch_res.json()["task_id"]

        # Attempt resume as Auditor
        resume_res = client.post(
            f"/api/tasks/{task_id}/resume",
            json={"decision": "approve", "notes": "Auditor trying to approve"},
            headers=_auth_header(UserRole.AUDITOR),
        )
        assert resume_res.status_code == 403
