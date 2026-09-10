"""
tests/test_network/test_telemetry_sink.py
Unit tests verifying audit ledger sink escalation on policy DENY events.
"""
from collections import namedtuple
from pathlib import Path
import socket
from unittest.mock import patch
from sovereign.audit.ledger import AuditLedger
from sovereign.audit.verifier import verify_ledger
from sovereign.config.settings import DEFAULT_POLICY_PATH
from sovereign.network.monitor import NetworkMonitor
from sovereign.network.policy import NetworkPolicyEngine
from sovereign.network.ring_buffer import ConnectionRingBuffer

Addr = namedtuple("Addr", ["ip", "port"])
Conn = namedtuple("Conn", ["fd", "family", "type", "laddr", "raddr", "status", "pid"])


def test_deny_events_sink_to_audit_ledger(temp_dir: Path):
    """Verify that only DENY events trigger audit ledger entries, with unbroken chaining."""
    ledger_path = temp_dir / "audit_ledger.jsonl"
    audit_ledger = AuditLedger(ledger_path)

    engine = NetworkPolicyEngine(DEFAULT_POLICY_PATH)
    ring_buffer = ConnectionRingBuffer(capacity=50)
    monitor = NetworkMonitor(policy_engine=engine, ring_buffer=ring_buffer, audit_ledger=audit_ledger)

    # 1 Allow (loopback), 1 Deny (public IP 1.1.1.1), 1 Allow (intranet), 1 Deny (port 53)
    mock_conns = [
        Conn(1, socket.AF_INET, socket.SOCK_STREAM, Addr("127.0.0.1", 80), Addr("127.0.0.1", 1234), "ESTABLISHED", 101),
        Conn(2, socket.AF_INET, socket.SOCK_STREAM, Addr("192.168.1.10", 4000), Addr("1.1.1.1", 443), "SYN_SENT", 102),
        Conn(3, socket.AF_INET, socket.SOCK_STREAM, Addr("10.0.0.1", 80), Addr("10.0.0.2", 8080), "ESTABLISHED", 103),
        Conn(4, socket.AF_INET, socket.SOCK_DGRAM, Addr("127.0.0.1", 5300), Addr("8.8.8.8", 53), "NONE", 104),
    ]

    with patch("psutil.net_connections", return_value=mock_conns):
        with patch.object(monitor, "_resolve_process_name", return_value="curl.exe"):
            events = monitor.poll_once()

    assert len(events) == 4
    # All 4 events must be in ring buffer
    assert ring_buffer.count() == 4
    assert ring_buffer.allowed_count == 2
    assert ring_buffer.denied_count == 2

    # Exactly the 2 DENY events must be committed to audit_ledger.jsonl
    assert ledger_path.exists()
    res = verify_ledger(ledger_path)
    assert res.is_valid is True
    assert res.records_checked == 2

    # Verify audit event details
    import json
    with open(ledger_path, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    assert len(records) == 2
    assert records[0]["event_type"] == "SECURITY_ALERT_NETWORK_DENY"
    assert records[0]["payload"]["remote_ip"] == "1.1.1.1"
    assert records[0]["payload"]["policy_reason"] == "public_egress_default_deny"

    assert records[1]["event_type"] == "SECURITY_ALERT_NETWORK_DENY"
    assert records[1]["payload"]["remote_ip"] == "8.8.8.8"
    assert records[1]["payload"]["policy_reason"] == "port_53_strictly_denied"
