"""
tests/test_network/test_egress_suite.py
Unit and CLI integration tests for synthetic multi-protocol egress probe suite.
"""
from pathlib import Path
import socket
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from sovereign.audit.ledger import AuditLedger
from sovereign.cli import cli
from sovereign.network.models import ProbeResult
from sovereign.network.test_egress import EgressTestHarness, run_egress_probes


def test_egress_probe_blocked_on_timeout():
    """Verify that socket timeouts are treated as BLOCKED (air-gap enforced)."""
    harness = EgressTestHarness()

    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = socket.timeout("timed out")
        mock_sock.sendto.side_effect = socket.timeout("timed out")
        mock_sock_cls.return_value = mock_sock

        dns_res = harness.probe_dns(host="8.8.8.8", port=53, timeout=0.1)
        assert dns_res.outcome == "BLOCKED"
        assert "timed out" in dns_res.reason

        http_res = harness.probe_http(host="1.1.1.1", port=80, timeout=0.1)
        assert http_res.outcome == "BLOCKED"
        assert "timed out" in http_res.reason

        https_res = harness.probe_https(host="1.1.1.1", port=443, timeout=0.1)
        assert https_res.outcome == "BLOCKED"

        ntp_res = harness.probe_ntp(host="129.6.15.28", port=123, timeout=0.1)
        assert ntp_res.outcome == "BLOCKED"

        raw_res = harness.probe_raw_socket(host="8.8.4.4", port=9999, timeout=0.1)
        assert raw_res.outcome == "BLOCKED"


def test_egress_probe_detects_leak_on_successful_connect():
    """Verify that a successful TCP or UDP response is correctly flagged as LEAKED."""
    harness = EgressTestHarness()

    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        # TCP connect succeeds without exception
        mock_sock.connect.return_value = None
        # UDP recvfrom receives response data
        mock_sock.recvfrom.return_value = (b"\xaa\xbb\x81\x80" + b"\x00" * 20, ("8.8.8.8", 53))
        mock_sock_cls.return_value = mock_sock

        dns_res = harness.probe_dns(host="8.8.8.8", port=53, timeout=0.1)
        assert dns_res.outcome == "LEAKED"
        assert "Received" in dns_res.reason

        http_res = harness.probe_http(host="1.1.1.1", port=80, timeout=0.1)
        assert http_res.outcome == "LEAKED"
        assert "TCP connection successfully established" in http_res.reason


def test_run_all_probes_structure(temp_dir: Path):
    """Verify run_all_probes returns 6 structured probe results and logs denials."""
    ledger_path = temp_dir / "audit_ledger.jsonl"
    ledger = AuditLedger(ledger_path)
    harness = EgressTestHarness(audit_ledger=ledger)

    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError("refused")
        mock_sock.sendto.side_effect = socket.timeout("timed out")
        mock_sock_cls.return_value = mock_sock

        results = harness.run_all_probes(timeout=0.1)

    assert len(results) == 6
    assert all(r.outcome == "BLOCKED" for r in results)

    # Check that audit ledger captured the denials
    import json
    with open(ledger_path, "r", encoding="utf-8") as f:
        records = [json.loads(l) for l in f if l.strip()]

    assert len(records) == 6
    assert all(r["event_type"] == "SECURITY_ALERT_NETWORK_DENY" for r in records)


def test_cli_network_status():
    """Verify `sovereign network status` CLI output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["network", "status"])
    assert result.exit_code == 0
    assert "=== Sovereign Network Isolation Policy ===" in result.output
    assert "Policy Name          : sovereign_default_deny" in result.output
    assert "Denied Ports         : [53]" in result.output


def test_cli_test_egress_command(temp_dir: Path):
    """Verify `sovereign test-egress` CLI output and exit codes."""
    runner = CliRunner()
    ledger_path = temp_dir / "audit_ledger.jsonl"

    # Case 1: All blocked -> exit 0
    with patch("sovereign.cli.run_egress_probes") as mock_probes:
        mock_probes.return_value = [
            ProbeResult(protocol="dns_udp", target_host="8.8.8.8", target_port=53, outcome="BLOCKED", reason="timed out", latency_ms=10.0),
            ProbeResult(protocol="http_tcp", target_host="1.1.1.1", target_port=80, outcome="BLOCKED", reason="timed out", latency_ms=12.0),
        ]
        result = runner.invoke(cli, ["test-egress", "--ledger-path", str(ledger_path)])
        assert result.exit_code == 0
        assert "[SECURE] 100% of outbound synthetic connections blocked." in result.output

    # Case 2: One leak -> exit 1
    with patch("sovereign.cli.run_egress_probes") as mock_probes:
        mock_probes.return_value = [
            ProbeResult(protocol="dns_udp", target_host="8.8.8.8", target_port=53, outcome="BLOCKED", reason="timed out", latency_ms=10.0),
            ProbeResult(protocol="http_tcp", target_host="1.1.1.1", target_port=80, outcome="LEAKED", reason="connected", latency_ms=5.0),
        ]
        result = runner.invoke(cli, ["test-egress", "--ledger-path", str(ledger_path)])
        assert result.exit_code == 1
        assert "[SECURITY ALERT] Unpermitted outbound connection succeeded!" in result.output
