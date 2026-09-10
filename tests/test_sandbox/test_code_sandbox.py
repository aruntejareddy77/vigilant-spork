"""
tests/test_sandbox/test_code_sandbox.py
Unit and security tests for CodeSandbox isolated execution, timeouts, and network blocks.
"""
import json
from pathlib import Path
import pytest
from sovereign.sandbox.executor import (
    CodeSandbox,
    SandboxSecurityViolation,
    validate_script_safety,
)
from sovereign.audit.ledger import AuditLedger


def test_benign_python_script_execution():
    """Test successful execution of benign calculation script."""
    sandbox = CodeSandbox(timeout_seconds=5.0)
    code = """
import math
results = [math.sqrt(x) for x in [4, 9, 16, 25]]
print(f"Calculated: {results}")
"""
    result = sandbox.execute(code)
    assert result.exit_code == 0
    assert "Calculated: [2.0, 3.0, 4.0, 5.0]" in result.stdout
    assert not result.timed_out
    assert result.duration_seconds > 0


def test_file_input_and_output_capture():
    """Test that input files are mounted and output files are captured."""
    sandbox = CodeSandbox(timeout_seconds=5.0)
    input_files = {
        "data.txt": "10\n20\n30",
    }
    code = """
with open("data.txt", "r") as f:
    numbers = [int(line.strip()) for line in f if line.strip()]

total = sum(numbers)
with open("result.txt", "w") as f:
    f.write(f"SUM={total}")
print(f"Computed sum: {total}")
"""
    result = sandbox.execute(code, input_files=input_files)
    assert result.exit_code == 0
    assert "Computed sum: 60" in result.stdout
    assert "result.txt" in result.output_files
    assert result.output_files["result.txt"].decode("utf-8") == "SUM=60"


def test_timeout_bounding_infinite_loop():
    """Test that long-running or infinite loops are forcefully halted at timeout."""
    sandbox = CodeSandbox(timeout_seconds=0.5)
    code = """
import time
time.sleep(10.0)
print("Finished")
"""
    result = sandbox.execute(code)
    assert result.timed_out is True
    assert result.exit_code == -1
    assert "Execution timed out" in result.stderr
    assert "Finished" not in result.stdout


def test_network_import_static_blocking():
    """Verify that socket and HTTP library imports are blocked statically before execution."""
    sandbox = CodeSandbox()

    # socket
    with pytest.raises(SandboxSecurityViolation, match="Network import prohibited"):
        sandbox.execute("import socket\ns = socket.socket()")

    # requests
    with pytest.raises(SandboxSecurityViolation, match="Network import prohibited"):
        sandbox.execute("import requests\nrequests.get('http://127.0.0.1')")

    # urllib
    with pytest.raises(SandboxSecurityViolation, match="Network import prohibited"):
        sandbox.execute("from urllib.request import urlopen\nurlopen('http://evil.com')")

    # aiohttp
    with pytest.raises(SandboxSecurityViolation, match="Network import prohibited"):
        sandbox.execute("import aiohttp\nprint('connected')")


def test_syntax_error_validation():
    """Verify invalid syntax raises ValueError."""
    sandbox = CodeSandbox()
    with pytest.raises(ValueError, match="invalid Python syntax"):
        sandbox.execute("def broken_syntax(")


def test_sandbox_audit_logging(tmp_path: Path):
    """Test that sandbox executions record an immutable event in the AuditLedger."""
    ledger_file = tmp_path / "sandbox_audit.jsonl"
    ledger = AuditLedger(ledger_file)
    sandbox = CodeSandbox(timeout_seconds=5.0, audit_ledger=ledger)

    code = "print('Audit test executed')"
    result = sandbox.execute(code, session_id="test-session-xyz")
    assert result.exit_code == 0

    with open(ledger_file, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    assert len(lines) == 1
    assert lines[0]["event_type"] == "CODE_EXECUTION"
    assert lines[0]["session_id"] == "test-session-xyz"
    assert lines[0]["actor_role"] == "sandbox"
    assert lines[0]["payload"]["exit_code"] == 0
