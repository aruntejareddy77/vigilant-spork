"""
tests/test_orchestration/test_workflow_cli.py
Integration tests for sovereign tool and workflow CLI subcommands.
"""
from pathlib import Path
from click.testing import CliRunner
from sovereign.cli import cli


def test_cli_tool_list_all(tmp_path: Path):
    """Test 'sovereign tool list' command output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["tool", "list", "--workspace", str(tmp_path)])
    assert result.exit_code == 0
    assert "execute_calculation" in result.output
    assert "read_file" in result.output
    assert "write_file" in result.output
    assert "parse_table" in result.output


def test_cli_tool_list_filtered_by_role(tmp_path: Path):
    """Test role filtering in 'sovereign tool list --role auditor'."""
    runner = CliRunner()
    result = runner.invoke(cli, ["tool", "list", "--role", "auditor", "--workspace", str(tmp_path)])
    assert result.exit_code == 0
    assert "execute_calculation" in result.output
    assert "parse_table" in result.output
    assert "read_file" not in result.output  # read_file requires ENGINEER


def test_cli_tool_inspect(tmp_path: Path):
    """Test 'sovereign tool inspect <tool>' output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["tool", "inspect", "execute_calculation", "--workspace", str(tmp_path)])
    assert result.exit_code == 0
    assert "Tool Name    : execute_calculation" in result.output
    assert "Parameters Schema:" in result.output
    assert '"expression"' in result.output

    # Non-existent tool
    err_result = runner.invoke(cli, ["tool", "inspect", "ghost_tool"])
    assert err_result.exit_code != 0
    assert "not found" in err_result.output


def test_cli_workflow_run_and_complete(tmp_path: Path):
    """Test 'sovereign workflow run' with automatic completion."""
    db_file = tmp_path / "cli_test.sqlite"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["workflow", "run", "calculate 12 * 8", "--db", str(db_file), "--thread-id", "calc-01"],
    )
    assert result.exit_code == 0
    assert "Thread ID : calc-01" in result.output
    assert "Status    : COMPLETED" in result.output
    assert "Calculation Result: 96" in result.output


def test_cli_workflow_run_hitl_and_resume(tmp_path: Path):
    """Test running workflow to HITL suspension and resuming via CLI."""
    db_file = tmp_path / "cli_hitl.sqlite"
    ledger_file = tmp_path / "cli_audit.jsonl"
    runner = CliRunner()

    # 1. Run until suspension
    run_res = runner.invoke(
        cli,
        [
            "workflow",
            "run",
            "Generate monthly compliance report",
            "--db",
            str(db_file),
            "--ledger",
            str(ledger_file),
            "--thread-id",
            "report-thread-1",
        ],
    )
    assert run_res.exit_code == 0
    assert "Status    : SUSPENDED" in run_res.output
    assert "Human-in-the-Loop approval gate" in run_res.output

    # 2. List threads
    list_res = runner.invoke(cli, ["workflow", "list", "--db", str(db_file)])
    assert list_res.exit_code == 0
    assert "report-thread-1" in list_res.output
    assert "SUSPENDED" in list_res.output

    # 3. Resume with rejection
    # First create a second thread to reject
    runner.invoke(
        cli,
        [
            "workflow",
            "run",
            "Generate draft release report",
            "--db",
            str(db_file),
            "--thread-id",
            "reject-thread-1",
        ],
    )
    rej_res = runner.invoke(
        cli,
        [
            "workflow",
            "resume",
            "reject-thread-1",
            "--decision",
            "reject",
            "--notes",
            "Invalid emission numbers",
            "--db",
            str(db_file),
        ],
    )
    assert rej_res.exit_code == 0
    assert "Status    : FAILED" in rej_res.output
    assert "Rejected" in rej_res.output

    # 4. Resume first thread with approval
    app_res = runner.invoke(
        cli,
        [
            "workflow",
            "resume",
            "report-thread-1",
            "--decision",
            "approve",
            "--notes",
            "Signed off by Chief Auditor",
            "--db",
            str(db_file),
            "--ledger",
            str(ledger_file),
        ],
    )
    assert app_res.exit_code == 0
    assert "Status    : COMPLETED" in app_res.output
