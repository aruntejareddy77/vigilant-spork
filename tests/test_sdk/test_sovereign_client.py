"""
tests/test_sdk/test_sovereign_client.py
Integration and unit tests for the lightweight Sovereign Python SDK.
Verifies complete task lifecycle, VRAM monitoring, audit verification,
directory traversal defense, and least-privilege RBAC enforcement.
"""
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from sovereign.sdk import (
    AuditVerificationResult,
    NetworkTelemetryResult,
    RBACPermissionError,
    SovereignAPIError,
    SovereignClient,
    SovereignConnectionError,
    TaskResult,
    TaskStatus,
    UserRole,
    VRAMStatus,
)


# ==========================================
# Client Initialization & Zero-Dep Tests
# ==========================================

def test_client_init_defaults():
    """Verify SovereignClient initialization with default engineer role."""
    client = SovereignClient(base_url="http://127.0.0.1:8000")
    assert client.base_url == "http://127.0.0.1:8000"
    assert client.role == UserRole.ENGINEER
    assert client.token is None
    assert client.timeout == 30.0
    assert hasattr(client, "tasks")
    assert hasattr(client, "models")
    assert hasattr(client, "network")
    assert hasattr(client, "audit")


def test_client_init_custom_role_and_token():
    """Verify initializing client with custom string role and bearer token."""
    client = SovereignClient(
        base_url="http://10.0.0.5:8000/",
        role="admin",
        token="sovg_admin_sec123",
        timeout=15.0,
    )
    assert client.base_url == "http://10.0.0.5:8000"
    assert client.role == UserRole.ADMIN
    assert client.token == "sovg_admin_sec123"
    assert client.timeout == 15.0


# ==========================================
# Task Lifecycle Tests (Engineer Role)
# ==========================================

def test_task_submit_success():
    """Verify task submission returns typed TaskResult."""
    client = SovereignClient(role=UserRole.ENGINEER)
    with patch.object(client, "_request") as mock_req:
        mock_req.return_value = {
            "task_id": "task-sdk-001",
            "thread_id": "wf-sdk-001",
            "status": "QUEUED",
        }
        res = client.tasks.submit("Parse industrial sensor CSV", files=["data.csv"])
        assert isinstance(res, TaskResult)
        assert res.task_id == "task-sdk-001"
        assert res.thread_id == "wf-sdk-001"
        assert res.status == TaskStatus.QUEUED
        mock_req.assert_called_once_with(
            "POST",
            "/api/tasks",
            payload={"prompt": "Parse industrial sensor CSV", "files": ["data.csv"], "model_override": None},
        )


def test_task_get_status():
    """Verify get_status returns steps, status, and pending approval."""
    client = SovereignClient(role=UserRole.ENGINEER)
    with patch.object(client, "_request") as mock_req:
        mock_req.return_value = {
            "task_id": "task-sdk-002",
            "status": "RUNNING",
            "steps": [
                {"step_index": 1, "node_name": "code_gen", "thought": "Generating Python script", "status": "COMPLETED"}
            ],
            "pending_approval": None,
            "artifacts": ["script.py"],
        }
        res = client.tasks.get_status("task-sdk-002")
        assert isinstance(res, TaskResult)
        assert res.task_id == "task-sdk-002"
        assert res.status == TaskStatus.RUNNING
        assert res.output == "Generating Python script"
        assert len(res.steps) == 1
        assert "script.py" in res.artifacts


def test_task_wait_for_completion():
    """Verify wait_for_completion polls until terminal status is reached."""
    client = SovereignClient(role=UserRole.ENGINEER)
    with patch.object(client.tasks, "get_status") as mock_status:
        mock_status.side_effect = [
            TaskResult(task_id="task-003", status=TaskStatus.RUNNING),
            TaskResult(task_id="task-003", status=TaskStatus.COMPLETED, output="All done"),
        ]
        res = client.tasks.wait_for_completion("task-003", poll_interval=0.01)
        assert res.status == TaskStatus.COMPLETED
        assert res.output == "All done"
        assert mock_status.call_count == 2


def test_task_approve():
    """Verify HITL deliverable approval via SDK."""
    client = SovereignClient(role=UserRole.ENGINEER)
    with patch.object(client, "_request") as mock_req:
        mock_req.return_value = {
            "task_id": "task-sdk-004",
            "decision": "approve",
            "status": "COMPLETED",
        }
        res = client.tasks.approve("task-sdk-004", notes="Code reviewed and verified")
        assert isinstance(res, TaskResult)
        assert res.status == TaskStatus.COMPLETED
        mock_req.assert_called_once_with(
            "POST",
            "/api/tasks/task-sdk-004/resume",
            payload={"decision": "approve", "notes": "Code reviewed and verified"},
        )


def test_task_reject():
    """Verify HITL deliverable rejection via SDK."""
    client = SovereignClient(role=UserRole.ENGINEER)
    with patch.object(client, "_request") as mock_req:
        mock_req.return_value = {
            "task_id": "task-sdk-005",
            "decision": "reject",
            "status": "REJECTED",
        }
        res = client.tasks.reject("task-sdk-005", reason="Unit test failed")
        assert isinstance(res, TaskResult)
        assert res.status == TaskStatus.REJECTED
        mock_req.assert_called_once_with(
            "POST",
            "/api/tasks/task-sdk-005/resume",
            payload={"decision": "reject", "notes": "Unit test failed"},
        )


def test_download_artifact_success(tmp_path):
    """Verify downloading an artifact writes to destination within target dir."""
    client = SovereignClient(role=UserRole.ENGINEER)
    with patch.object(client, "_request") as mock_req:
        mock_req.return_value = {"task_id": "task-1", "content": "verified deliverable data"}
        dest_file = client.tasks.download_artifact(
            task_id="task-1",
            filename="output_memo.json",
            output_dir=str(tmp_path),
        )
        assert dest_file.exists()
        assert dest_file.is_file()
        assert "verified deliverable data" in dest_file.read_text(encoding="utf-8")


def test_download_artifact_path_traversal_blocked(tmp_path):
    """Verify directory traversal is strictly blocked with ValueError (T-05-08)."""
    client = SovereignClient(role=UserRole.ENGINEER)
    with pytest.raises(ValueError, match="Path traversal detected"):
        client.tasks.download_artifact(
            task_id="task-1",
            filename="../../etc/passwd",
            output_dir=str(tmp_path),
        )


# ==========================================
# Models, Network, and Audit Namespaces
# ==========================================

def test_models_vram_status():
    """Verify vram_status returns typed VRAMStatus object."""
    client = SovereignClient(role=UserRole.AUDITOR)
    with patch.object(client, "_request") as mock_req:
        mock_req.return_value = {
            "total_mb": 24576,
            "usable_mb": 22528,
            "allocated_mb": 8192,
            "available_mb": 14336,
            "loaded_models": [{"model_id": "qwen2.5-7b-instruct", "vram_mb": 8192}],
        }
        res = client.models.vram_status()
        assert isinstance(res, VRAMStatus)
        assert res.total_mb == 24576
        assert res.usable_mb == 22528
        assert res.allocated_mb == 8192
        assert res.available_mb == 14336
        assert len(res.loaded_models) == 1


def test_network_get_status_and_telemetry():
    """Verify network namespace methods return expected schemas."""
    client = SovereignClient(role=UserRole.AUDITOR)
    with patch.object(client, "_request") as mock_req:
        mock_req.return_value = {
            "policy_name": "sovereign_default_deny",
            "default_action": "DENY",
            "allowed_loopback": ["127.0.0.0/8"],
        }
        status = client.network.get_status()
        assert status["policy_name"] == "sovereign_default_deny"

    with patch.object(client, "_request") as mock_req:
        mock_req.return_value = {
            "recent_events": [
                {
                    "timestamp_iso": "2026-09-14T12:00:00Z",
                    "protocol": "tcp",
                    "local_address": "127.0.0.1:54321",
                    "remote_address": "8.8.8.8:53",
                    "pid": 1234,
                    "process_name": "curl",
                    "verdict": "BLOCKED",
                    "reason": "Default-deny policy",
                }
            ]
        }
        telemetry = client.network.get_telemetry()
        assert len(telemetry) == 1
        assert isinstance(telemetry[0], NetworkTelemetryResult)
        assert telemetry[0].verdict == "BLOCKED"
        assert telemetry[0].process_name == "curl"


def test_audit_verify():
    """Verify audit verification returns typed AuditVerificationResult."""
    client = SovereignClient(role=UserRole.AUDITOR)
    with patch.object(client, "_request") as mock_req:
        mock_req.return_value = {
            "is_valid": True,
            "records_checked": 42,
            "tip_hash": "a" * 64,
            "error_message": None,
        }
        res = client.audit.verify()
        assert isinstance(res, AuditVerificationResult)
        assert res.is_valid is True
        assert res.records_checked == 42
        assert res.tip_hash == "a" * 64


def test_audit_export_session(tmp_path):
    """Verify audit export writes json records to disk."""
    client = SovereignClient(role=UserRole.AUDITOR)
    out_file = tmp_path / "session_audit.json"
    with patch.object(client, "_request") as mock_req:
        mock_req.return_value = {"session_id": "sess-1", "events": [{"event_type": "TASK_START"}]}
        dest = client.audit.export_session("sess-1", out_file)
        assert dest.exists()
        assert "TASK_START" in dest.read_text(encoding="utf-8")


# ==========================================
# RBAC Enforcement Tests (UI-05)
# ==========================================

def test_auditor_client_side_blocking_submit():
    """Verify Auditor role raises RBACPermissionError before issuing network request."""
    client = SovereignClient(role=UserRole.AUDITOR)
    with patch.object(client, "_request") as mock_req:
        with pytest.raises(RBACPermissionError, match="Auditor role is restricted from submitting tasks"):
            client.tasks.submit("Attempting task submission as auditor")
        mock_req.assert_not_called()


def test_auditor_client_side_blocking_approve():
    """Verify Auditor role raises RBACPermissionError before approving task."""
    client = SovereignClient(role=UserRole.AUDITOR)
    with patch.object(client, "_request") as mock_req:
        with pytest.raises(RBACPermissionError, match="Auditor role is restricted from approving tasks"):
            client.tasks.approve("task-001", notes="Auditor trying to approve")
        mock_req.assert_not_called()


def test_auditor_client_side_blocking_reject():
    """Verify Auditor role raises RBACPermissionError before rejecting task."""
    client = SovereignClient(role=UserRole.AUDITOR)
    with patch.object(client, "_request") as mock_req:
        with pytest.raises(RBACPermissionError, match="Auditor role is restricted from rejecting tasks"):
            client.tasks.reject("task-001", reason="Auditor trying to reject")
        mock_req.assert_not_called()


def test_auditor_allowed_read_only_operations():
    """Verify Auditor role can inspect audit and network status without error."""
    client = SovereignClient(role=UserRole.AUDITOR)
    with patch.object(client, "_request") as mock_req:
        mock_req.return_value = {"total_records": 10, "status": "healthy"}
        info = client.audit.inspect()
        assert info["status"] == "healthy"

    with patch.object(client, "_request") as mock_req:
        mock_req.return_value = {"all_blocked": True}
        egress = client.network.run_egress_test()
        assert egress["all_blocked"] is True


# ==========================================
# Error Handling & Network Resilience
# ==========================================

def test_server_403_translated_to_rbac_permission_error():
    """Verify HTTP 403 response from backend translates to RBACPermissionError."""
    client = SovereignClient(role=UserRole.ENGINEER)

    # Simulate urllib HTTPError 403
    fp = io.BytesIO(json.dumps({"detail": "Access denied: Insufficient clearance"}).encode("utf-8"))
    http_err = urllib.error.HTTPError(
        url="http://127.0.0.1:8000/api/tasks",
        code=403,
        msg="Forbidden",
        hdrs={},
        fp=fp,
    )

    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(RBACPermissionError, match="Access denied \\(403 Forbidden\\)"):
            client.tasks.submit("Submit task that server rejects")


def test_connection_failure_raises_sovereign_connection_error():
    """Verify unreachable server translates to SovereignConnectionError."""
    client = SovereignClient(role=UserRole.ENGINEER)
    url_err = urllib.error.URLError(reason="Connection refused")

    with patch("urllib.request.urlopen", side_effect=url_err):
        with pytest.raises(SovereignConnectionError, match="Failed to connect"):
            client.models.vram_status()
