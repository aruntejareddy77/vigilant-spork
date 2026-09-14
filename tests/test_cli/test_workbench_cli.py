"""
tests/test_cli/test_workbench_cli.py
Integration tests for Sovereign Workbench CLI commands:
serve, task submit, task status, task logs, task approve, task reject, model vram.
"""
from unittest.mock import MagicMock, patch
import pytest
from click.testing import CliRunner

from sovereign.cli import cli


# ==========================================
# Sovereign Serve Command Tests
# ==========================================

def test_cli_serve_fails_on_all_interfaces():
    """Verify sovereign serve fails closed on 0.0.0.0 per UI-02."""
    runner = CliRunner()
    res = runner.invoke(cli, ["serve", "--host", "0.0.0.0"])
    assert res.exit_code == 1
    assert "Security Binding Violation" in res.output or "strictly prohibited" in res.output


def test_cli_serve_fails_on_ipv6_all_interfaces():
    """Verify sovereign serve fails closed on :: per UI-02."""
    runner = CliRunner()
    res = runner.invoke(cli, ["serve", "--host", "::"])
    assert res.exit_code == 1
    assert "Security Binding Violation" in res.output or "strictly prohibited" in res.output


def test_cli_serve_fails_on_unauthorized_ip():
    """Verify sovereign serve fails closed on non-intranet IP."""
    runner = CliRunner()
    res = runner.invoke(cli, ["serve", "--host", "8.8.8.8"])
    assert res.exit_code == 1
    assert "Security Binding Violation" in res.output


def test_cli_serve_valid_loopback_starts_uvicorn():
    """Verify sovereign serve with 127.0.0.1 calls uvicorn.run."""
    runner = CliRunner()
    with patch("uvicorn.run") as mock_uvicorn:
        res = runner.invoke(cli, ["serve", "--host", "127.0.0.1", "--port", "8000"])
        assert res.exit_code == 0
        mock_uvicorn.assert_called_once_with(
            "sovereign.server.app:create_app",
            host="127.0.0.1",
            port=8000,
            factory=True,
            workers=1,
            reload=False,
        )


# ==========================================
# Sovereign Task Command Tests
# ==========================================

def test_cli_task_submit_blocks_auditor():
    """Verify Auditor role is immediately halted with exit code 1 per UI-05."""
    runner = CliRunner()
    res = runner.invoke(cli, ["task", "submit", "--role", "auditor", "Generate analysis"])
    assert res.exit_code == 1
    assert "[ERROR] Auditor role is restricted from submitting tasks per least-privilege policy (UI-05)" in res.output


def test_cli_task_approve_blocks_auditor():
    """Verify Auditor role is immediately halted from approving tasks."""
    runner = CliRunner()
    res = runner.invoke(cli, ["task", "approve", "--role", "auditor", "task-999"])
    assert res.exit_code == 1
    assert "[ERROR] Auditor role is restricted from approving tasks per least-privilege policy (UI-05)" in res.output


def test_cli_task_reject_blocks_auditor():
    """Verify Auditor role is immediately halted from rejecting tasks."""
    runner = CliRunner()
    res = runner.invoke(cli, ["task", "reject", "--role", "auditor", "task-999"])
    assert res.exit_code == 1
    assert "[ERROR] Auditor role is restricted from rejecting tasks per least-privilege policy (UI-05)" in res.output


def test_cli_task_submit_engineer_success():
    """Verify Engineer role submits task and displays task ID."""
    runner = CliRunner()
    with patch("sovereign.cli._send_api_request") as mock_api:
        mock_api.return_value = {
            "task_id": "task-abc12345",
            "thread_id": "wf-xyz67890",
            "status": "QUEUED",
        }
        res = runner.invoke(cli, ["task", "submit", "--role", "engineer", "Analyze vibration report"])
        assert res.exit_code == 0
        assert "task-abc12345" in res.output
        assert "wf-xyz67890" in res.output
        assert "QUEUED" in res.output


def test_cli_task_submit_with_streaming():
    """Verify --stream flag polls and prints live steps."""
    runner = CliRunner()
    with patch("sovereign.cli._send_api_request") as mock_api:
        mock_api.side_effect = [
            {"task_id": "task-stream-1", "thread_id": "wf-1", "status": "QUEUED"},
            {
                "task_id": "task-stream-1",
                "status": "COMPLETED",
                "steps": [
                    {
                        "step_index": 1,
                        "node_name": "ocr_extraction",
                        "thought": "Extracting inspection findings table",
                        "status": "COMPLETED",
                    }
                ],
            },
        ]
        res = runner.invoke(cli, ["task", "submit", "--stream", "Process report.pdf"])
        assert res.exit_code == 0
        assert "task-stream-1" in res.output
        assert "Extracting inspection findings table" in res.output
        assert "Task finished with status: COMPLETED" in res.output


def test_cli_task_status_display():
    """Verify sovereign task status displays details, completed steps, and artifacts."""
    runner = CliRunner()
    with patch("sovereign.cli._send_api_request") as mock_api:
        mock_api.return_value = {
            "task_id": "task-test-456",
            "status": "RUNNING",
            "steps": [{"node_name": "rag_search", "status": "COMPLETED"}],
            "pending_approval": None,
            "artifacts": ["deliverable.docx"],
        }
        res = runner.invoke(cli, ["task", "status", "task-test-456"])
        assert res.exit_code == 0
        assert "=== Sovereign Task Status: task-test-456 ===" in res.output
        assert "Status           : RUNNING" in res.output
        assert "Completed Steps  : 1" in res.output
        assert "Artifacts        : deliverable.docx" in res.output


def test_cli_task_status_pending_hitl_approval():
    """Verify sovereign task status highlights pending HITL gate."""
    runner = CliRunner()
    with patch("sovereign.cli._send_api_request") as mock_api:
        mock_api.return_value = {
            "task_id": "task-hitl-789",
            "status": "SUSPENDED",
            "steps": [],
            "pending_approval": {"action": "signoff", "deliverable": "Report.docx"},
            "artifacts": [],
        }
        res = runner.invoke(cli, ["task", "status", "task-hitl-789"])
        assert res.exit_code == 0
        assert "Human-in-the-Loop approval gate" in res.output
        assert "sovereign task approve task-hitl-789" in res.output


def test_cli_task_logs_display():
    """Verify sovereign task logs displays execution timeline."""
    runner = CliRunner()
    with patch("sovereign.cli._send_api_request") as mock_api:
        mock_api.return_value = {
            "task_id": "task-logs-101",
            "status": "COMPLETED",
            "steps": [
                {
                    "step_index": 1,
                    "node_name": "code_sandbox",
                    "status": "COMPLETED",
                    "elapsed_ms": 120.5,
                    "thought": "Executed sandbox script safely",
                }
            ],
        }
        res = runner.invoke(cli, ["task", "logs", "task-logs-101"])
        assert res.exit_code == 0
        assert "code_sandbox" in res.output
        assert "Executed sandbox script safely" in res.output


def test_cli_task_approve_success():
    """Verify sovereign task approve sends decision and prints resume confirmation."""
    runner = CliRunner()
    with patch("sovereign.cli._send_api_request") as mock_api:
        mock_api.return_value = {
            "task_id": "task-approve-202",
            "decision": "approve",
            "status": "COMPLETED",
        }
        res = runner.invoke(cli, ["task", "approve", "task-approve-202", "--notes", "Verified OK"])
        assert res.exit_code == 0
        assert "Resumed Task: task-approve-202" in res.output
        assert "Decision  : APPROVE" in res.output
        assert "Status    : COMPLETED" in res.output


def test_cli_task_reject_success():
    """Verify sovereign task reject sends decision and prints halt confirmation."""
    runner = CliRunner()
    with patch("sovereign.cli._send_api_request") as mock_api:
        mock_api.return_value = {
            "task_id": "task-reject-303",
            "decision": "reject",
            "status": "REJECTED",
        }
        res = runner.invoke(cli, ["task", "reject", "task-reject-303", "--reason", "Flawed calculation"])
        assert res.exit_code == 0
        assert "Resumed Task: task-reject-303" in res.output
        assert "Decision  : REJECT" in res.output
        assert "Status    : REJECTED" in res.output


# ==========================================
# Sovereign Model VRAM Command Tests
# ==========================================

def test_cli_model_vram_in_process():
    """Verify sovereign model vram command outputs required memory headroom metrics."""
    runner = CliRunner()
    res = runner.invoke(cli, ["model", "vram"])
    assert res.exit_code == 0
    assert "Total Budget" in res.output
    assert "Safety Reserve" in res.output
    assert "Usable Envelope" in res.output
    assert "Allocated MB" in res.output
    assert "Available Headroom" in res.output
    assert "Loaded Models" in res.output


def test_cli_model_vram_remote_query():
    """Verify sovereign model vram command queries remote server."""
    runner = CliRunner()
    with patch("sovereign.cli._send_api_request") as mock_api:
        mock_api.return_value = {
            "total_mb": 24576,
            "usable_mb": 22528,
            "allocated_mb": 7168,
            "available_mb": 15360,
            "loaded_models": [{"model_id": "qwen2.5-7b-instruct", "vram_mb": 7168}],
        }
        res = runner.invoke(cli, ["model", "vram", "--server-url", "http://127.0.0.1:8000"])
        assert res.exit_code == 0
        assert "Total Budget" in res.output
        assert "7,168 MB" in res.output
        assert "15,360 MB" in res.output
        assert "qwen2.5-7b-instruct" in res.output
