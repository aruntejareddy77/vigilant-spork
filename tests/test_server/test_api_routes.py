"""
tests/test_server/test_api_routes.py
Integration tests for all REST API routes with RBAC enforcement.
"""
import pytest
from fastapi.testclient import TestClient

from sovereign.server.app import create_app
from sovereign.server.auth.tokens import create_access_token
from sovereign.server.config import ServerConfig
from sovereign.tools.schemas import UserRole


SECRET = "test-secret-for-api-routes"


@pytest.fixture
def app():
    """Create a test FastAPI app."""
    config = ServerConfig(secret_key=SECRET)
    return create_app(server_config=config)


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


def _auth_header(role: UserRole):
    """Create an Authorization header for the given role."""
    token = create_access_token(role, SECRET)
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Health & Me Endpoints
# =============================================================================


class TestSystemEndpoints:
    """Tests for /api/health and /api/me."""

    def test_health_returns_200(self, client):
        """Health endpoint should return 200 OK."""
        response = client.get(
            "/api/health", headers={"host": "localhost:8000"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert data["service"] == "Sovereign AI Workbench"

    def test_me_returns_role(self, client):
        """Me endpoint should return the current role."""
        response = client.get(
            "/api/me?role=engineer", headers={"host": "localhost:8000"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "engineer"
        assert data["permissions"]["can_submit_tasks"] is True

    def test_me_auditor_permissions(self, client):
        """Auditor should not have task submission permission."""
        response = client.get(
            "/api/me?role=auditor", headers={"host": "localhost:8000"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["permissions"]["can_submit_tasks"] is False


# =============================================================================
# Task Endpoints
# =============================================================================


class TestTaskEndpoints:
    """Tests for task management API."""

    def test_submit_task_as_engineer(self, client):
        """Engineer should be able to submit tasks."""
        response = client.post(
            "/api/tasks",
            json={"prompt": "Extract findings from inspection report"},
            headers={**_auth_header(UserRole.ENGINEER), "host": "localhost:8000"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "QUEUED"

    def test_submit_task_as_auditor_denied(self, client):
        """Auditor should be denied task submission (403)."""
        response = client.post(
            "/api/tasks",
            json={"prompt": "Should be denied"},
            headers={**_auth_header(UserRole.AUDITOR), "host": "localhost:8000"},
        )
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

    def test_list_tasks_as_auditor(self, client):
        """Auditor should be able to list tasks."""
        response = client.get(
            "/api/tasks",
            headers={**_auth_header(UserRole.AUDITOR), "host": "localhost:8000"},
        )
        assert response.status_code == 200
        assert "tasks" in response.json()

    def test_task_status_and_resume(self, client):
        """Test task creation, status check, and resume flow."""
        # Create a task as engineer
        create_resp = client.post(
            "/api/tasks",
            json={"prompt": "Test task for resume"},
            headers={**_auth_header(UserRole.ENGINEER), "host": "localhost:8000"},
        )
        assert create_resp.status_code == 200
        task_id = create_resp.json()["task_id"]

        # Check status as auditor
        status_resp = client.get(
            f"/api/tasks/{task_id}",
            headers={**_auth_header(UserRole.AUDITOR), "host": "localhost:8000"},
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["task_id"] == task_id

        # Resume as engineer
        resume_resp = client.post(
            f"/api/tasks/{task_id}/resume",
            json={"decision": "approve", "notes": "Verified"},
            headers={**_auth_header(UserRole.ENGINEER), "host": "localhost:8000"},
        )
        assert resume_resp.status_code == 200
        assert resume_resp.json()["decision"] == "approve"


# =============================================================================
# Model Endpoints
# =============================================================================


class TestModelEndpoints:
    """Tests for model catalog and VRAM API."""

    def test_vram_endpoint(self, client):
        """VRAM endpoint should return memory metrics."""
        response = client.get(
            "/api/models/vram",
            headers={**_auth_header(UserRole.AUDITOR), "host": "localhost:8000"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_mb" in data
        assert "usable_mb" in data
        assert "allocated_mb" in data

    def test_list_models(self, client):
        """List models should return registered models."""
        response = client.get(
            "/api/models",
            headers={**_auth_header(UserRole.AUDITOR), "host": "localhost:8000"},
        )
        assert response.status_code == 200
        assert "models" in response.json()

    def test_register_model_as_admin(self, client):
        """Admin should be able to register models."""
        response = client.post(
            "/api/models/register",
            json={"model_id": "test-model", "engine": "mock"},
            headers={**_auth_header(UserRole.ADMIN), "host": "localhost:8000"},
        )
        assert response.status_code == 200
        assert response.json()["model_id"] == "test-model"

    def test_register_model_as_engineer_denied(self, client):
        """Engineer should be denied model registration (403)."""
        response = client.post(
            "/api/models/register",
            json={"model_id": "test-model", "engine": "mock"},
            headers={**_auth_header(UserRole.ENGINEER), "host": "localhost:8000"},
        )
        assert response.status_code == 403


# =============================================================================
# Network Endpoints
# =============================================================================


class TestNetworkEndpoints:
    """Tests for network policy and telemetry API."""

    def test_network_status(self, client):
        """Network status should return policy info."""
        response = client.get(
            "/api/network/status",
            headers={**_auth_header(UserRole.AUDITOR), "host": "localhost:8000"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["policy_name"] == "sovereign_default_deny"
        assert data["default_action"] == "DENY"

    def test_network_telemetry(self, client):
        """Telemetry endpoint should return telemetry snapshot."""
        response = client.get(
            "/api/network/telemetry",
            headers={**_auth_header(UserRole.AUDITOR), "host": "localhost:8000"},
        )
        assert response.status_code == 200

    def test_egress_test(self, client):
        """Egress test should return probe results."""
        response = client.post(
            "/api/network/test-egress",
            headers={**_auth_header(UserRole.AUDITOR), "host": "localhost:8000"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["all_blocked"] is True


# =============================================================================
# Audit Endpoints
# =============================================================================


class TestAuditEndpoints:
    """Tests for audit ledger API."""

    def test_audit_inspect(self, client):
        """Audit inspect should return ledger stats."""
        response = client.get(
            "/api/audit/inspect",
            headers={**_auth_header(UserRole.AUDITOR), "host": "localhost:8000"},
        )
        assert response.status_code == 200

    def test_audit_verify(self, client):
        """Audit verify should return verification result."""
        response = client.get(
            "/api/audit/verify",
            headers={**_auth_header(UserRole.AUDITOR), "host": "localhost:8000"},
        )
        assert response.status_code == 200
        assert response.json()["is_valid"] is True

    def test_audit_export(self, client):
        """Audit export should return records."""
        response = client.get(
            "/api/audit/export",
            headers={**_auth_header(UserRole.AUDITOR), "host": "localhost:8000"},
        )
        assert response.status_code == 200


# =============================================================================
# Preview & Demo Endpoints
# =============================================================================


class TestPreviewEndpoints:
    """Tests for document preview API."""

    def test_preview_document(self, client):
        """Preview should return bounding box metadata."""
        response = client.get(
            "/api/preview/test-doc-001",
            headers={**_auth_header(UserRole.AUDITOR), "host": "localhost:8000"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["doc_id"] == "test-doc-001"
        assert len(data["bounding_boxes"]) > 0


class TestDemoEndpoints:
    """Tests for demo launch API."""

    def test_launch_demo_a(self, client):
        """Engineer should be able to launch Demo A."""
        response = client.post(
            "/api/demos/demo_a/launch",
            headers={**_auth_header(UserRole.ENGINEER), "host": "localhost:8000"},
        )
        assert response.status_code == 200
        assert response.json()["demo_id"] == "demo_a"
        assert response.json()["status"] == "LAUNCHED"

    def test_launch_demo_as_auditor_denied(self, client):
        """Auditor should be denied demo launch (403)."""
        response = client.post(
            "/api/demos/demo_a/launch",
            headers={**_auth_header(UserRole.AUDITOR), "host": "localhost:8000"},
        )
        assert response.status_code == 403

    def test_launch_invalid_demo(self, client):
        """Invalid demo ID should return 404."""
        response = client.post(
            "/api/demos/demo_z/launch",
            headers={**_auth_header(UserRole.ENGINEER), "host": "localhost:8000"},
        )
        assert response.status_code == 404
