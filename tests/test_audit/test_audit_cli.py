"""
tests/test_audit/test_audit_cli.py
Unit and CLI integration tests for audit verification, inspection, and tamper protection.
"""
import json
from pathlib import Path
import pytest
from click.testing import CliRunner

from sovereign.audit.canonical import GENESIS_PREVIOUS_HASH
from sovereign.audit.ledger import AuditLedger
from sovereign.audit.mirror import AuditMirror
from sovereign.audit.verifier import (
    AuditTamperException,
    verify_ledger,
    verify_ledger_tip,
)
from sovereign.cli import cli


def test_verify_ledger_valid_chain(temp_dir: Path, sample_payload: dict):
    """Verify that verify_ledger confirms an uncorrupted ledger."""
    ledger_path = temp_dir / "audit_ledger.jsonl"
    ledger = AuditLedger(ledger_path)

    for i in range(5):
        ledger.append_event(
            session_id=f"session-{i % 2}",
            event_type="test_action",
            actor_role="user",
            payload={"i": i, "payload": sample_payload},
        )

    res = verify_ledger(ledger_path)
    assert res.is_valid is True
    assert res.records_checked == 5
    assert res.error_seq is None
    assert len(res.tip_hash) == 64


def test_verify_ledger_detects_payload_tamper(temp_dir: Path):
    """Verify that altering a payload byte causes verify_ledger to pinpoint the corrupted sequence."""
    ledger_path = temp_dir / "audit_ledger.jsonl"
    ledger = AuditLedger(ledger_path)

    for i in range(5):
        ledger.append_event("s1", "event", "admin", {"data": f"original_{i}"})

    # Tamper with line 2 (seq 2)
    with open(ledger_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    record_2 = json.loads(lines[2])
    record_2["payload"]["data"] = "tampered_data"
    lines[2] = json.dumps(record_2) + "\n"

    with open(ledger_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    res = verify_ledger(ledger_path)
    assert res.is_valid is False
    assert res.error_seq == 2
    assert "Tamper detected at seq 2" in res.error_message


def test_verify_ledger_tip_performance_and_accuracy(temp_dir: Path):
    """Verify verify_ledger_tip detects valid tip and corrupted tip."""
    ledger_path = temp_dir / "audit_ledger.jsonl"
    ledger = AuditLedger(ledger_path)

    is_valid, msg, tip = verify_ledger_tip(ledger_path)
    assert is_valid is True
    assert tip == GENESIS_PREVIOUS_HASH

    ledger.append_event("s1", "start", "sys", {"status": "ok"})
    is_valid, msg, tip = verify_ledger_tip(ledger_path)
    assert is_valid is True

    ledger.append_event("s1", "next", "sys", {"status": "running"})
    is_valid, msg, tip = verify_ledger_tip(ledger_path)
    assert is_valid is True

    # Tamper with the tip record
    with open(ledger_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    tip_record = json.loads(lines[-1])
    tip_record["payload"]["status"] = "injected"
    lines[-1] = json.dumps(tip_record) + "\n"

    with open(ledger_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    is_valid, msg, tip = verify_ledger_tip(ledger_path)
    assert is_valid is False
    assert "Tip corruption" in msg


def test_append_event_raises_on_tampered_ledger(temp_dir: Path):
    """Verify that AuditLedger.append_event fails closed if the tip is corrupted."""
    ledger_path = temp_dir / "audit_ledger.jsonl"
    ledger = AuditLedger(ledger_path)

    ledger.append_event("s1", "step_0", "user", {"val": 0})
    ledger.append_event("s1", "step_1", "user", {"val": 1})

    # Tamper with the tip
    with open(ledger_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    tip_rec = json.loads(lines[-1])
    tip_rec["entry_hash"] = "0" * 64
    lines[-1] = json.dumps(tip_rec) + "\n"

    with open(ledger_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    with pytest.raises(AuditTamperException) as exc_info:
        ledger.append_event("s1", "step_2", "user", {"val": 2})

    assert "Ledger tip integrity check failed" in str(exc_info.value)


def test_cli_audit_verify_success_and_failure(temp_dir: Path):
    """Test `sovereign audit verify` CLI command with exit codes."""
    runner = CliRunner()
    ledger_path = temp_dir / "audit_ledger.jsonl"
    ledger = AuditLedger(ledger_path)

    ledger.append_event("s1", "e0", "sys", {"ok": True})
    ledger.append_event("s1", "e1", "sys", {"ok": True})

    # Test clean ledger -> exit 0
    result = runner.invoke(cli, ["audit", "verify", str(ledger_path)])
    assert result.exit_code == 0
    assert "[OK] Audit ledger integrity verified." in result.output

    # Tamper with line 1
    with open(ledger_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    r1 = json.loads(lines[1])
    r1["payload"]["ok"] = False
    lines[1] = json.dumps(r1) + "\n"
    with open(ledger_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # Test tampered ledger -> exit 1
    result = runner.invoke(cli, ["audit", "verify", str(ledger_path)])
    assert result.exit_code == 1
    assert "[FAIL] Cryptographic audit chain TAMPER detected!" in result.output
    assert "Error Sequence : 1" in result.output


def test_cli_audit_inspect(temp_dir: Path):
    """Test `sovereign audit inspect` CLI command."""
    runner = CliRunner()
    ledger_path = temp_dir / "audit_ledger.jsonl"
    ledger = AuditLedger(ledger_path)

    ledger.append_event("session-alpha", "init", "admin", {"data": 123})
    ledger.append_event("session-beta", "action", "operator", {"data": 456})

    result = runner.invoke(cli, ["audit", "inspect", str(ledger_path)])
    assert result.exit_code == 0
    assert "Total Records    : 2" in result.output
    assert "Unique Sessions  : 2" in result.output
    assert "Genesis PrevHash :" in result.output


def test_cli_audit_export(temp_dir: Path):
    """Test `sovereign audit export` CLI command with JSON and JSONL formats."""
    runner = CliRunner()
    ledger_path = temp_dir / "audit_ledger.jsonl"
    db_path = temp_dir / "audit_index.sqlite"

    mirror = AuditMirror(db_path)
    ledger = AuditLedger(ledger_path=ledger_path, mirror=mirror)

    ledger.append_event("session-target", "step_1", "user", {"v": 1})
    ledger.append_event("session-other", "step_2", "user", {"v": 2})
    ledger.append_event("session-target", "step_3", "user", {"v": 3})

    # Test stdout export jsonl
    result = runner.invoke(
        cli,
        ["audit", "export", "--session-id", "session-target", "--ledger-path", str(ledger_path)],
    )
    assert result.exit_code == 0
    exported_lines = [json.loads(l) for l in result.output.strip().splitlines()]
    assert len(exported_lines) == 2
    assert exported_lines[0]["seq_num"] == 0
    assert exported_lines[1]["seq_num"] == 2

    # Test export to file via SQLite mirror
    output_file = temp_dir / "exported.json"
    result = runner.invoke(
        cli,
        [
            "audit",
            "export",
            "--session-id",
            "session-target",
            "--db-path",
            str(db_path),
            "--format",
            "json",
            "--output",
            str(output_file),
        ],
    )
    assert result.exit_code == 0
    assert output_file.exists()

    with open(output_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 2
    assert data[0]["seq_num"] == 0
    assert data[1]["seq_num"] == 2
