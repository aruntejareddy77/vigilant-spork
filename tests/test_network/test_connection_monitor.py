"""
tests/test_network/test_connection_monitor.py
Unit tests for psutil network monitor polling, PID resolution, and error handling.
"""
from collections import namedtuple
import socket
from unittest.mock import MagicMock, patch
import psutil
from sovereign.config.settings import DEFAULT_POLICY_PATH
from sovereign.network.monitor import NetworkMonitor
from sovereign.network.policy import NetworkPolicyEngine
from sovereign.network.ring_buffer import ConnectionRingBuffer

# Mock namedtuples matching psutil return structure
Addr = namedtuple("Addr", ["ip", "port"])
Conn = namedtuple("Conn", ["fd", "family", "type", "laddr", "raddr", "status", "pid"])


def test_monitor_poll_once_with_mocked_connections():
    """Verify monitor processes connections and evaluates policies properly."""
    engine = NetworkPolicyEngine(DEFAULT_POLICY_PATH)
    ring_buffer = ConnectionRingBuffer(capacity=50)
    monitor = NetworkMonitor(policy_engine=engine, ring_buffer=ring_buffer)

    mock_conns = [
        Conn(
            fd=1,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
            laddr=Addr("127.0.0.1", 8000),
            raddr=Addr("127.0.0.1", 54321),
            status="ESTABLISHED",
            pid=1001,
        ),
        Conn(
            fd=2,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
            laddr=Addr("192.168.1.50", 40000),
            raddr=Addr("8.8.8.8", 53),
            status="SYN_SENT",
            pid=1002,
        ),
        Conn(
            fd=3,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
            laddr=Addr("10.0.0.5", 30000),
            raddr=Addr("10.0.0.10", 5432),
            status="ESTABLISHED",
            pid=1003,
        ),
    ]

    with patch("psutil.net_connections", return_value=mock_conns):
        with patch.object(monitor, "_resolve_process_name", return_value="test_proc"):
            events = monitor.poll_once()

    assert len(events) == 3
    assert ring_buffer.count() == 3

    # Event 0: Loopback -> ALLOW
    assert events[0].verdict == "ALLOW"
    assert events[0].reason == "loopback_allowed"

    # Event 1: Port 53 -> DENY
    assert events[1].verdict == "DENY"
    assert events[1].reason == "port_53_strictly_denied"

    # Event 2: Intranet -> ALLOW
    assert events[2].verdict == "ALLOW"
    assert events[2].reason == "intranet_allowed"


def test_defensive_pid_resolution():
    """Verify AccessDenied, NoSuchProcess, and unexpected exceptions do not crash resolution."""
    engine = NetworkPolicyEngine(DEFAULT_POLICY_PATH)
    ring_buffer = ConnectionRingBuffer(capacity=50)
    monitor = NetworkMonitor(policy_engine=engine, ring_buffer=ring_buffer)

    # Test None / negative PID
    assert monitor._resolve_process_name(None) == "system/kernel"
    assert monitor._resolve_process_name(-1) == "system/kernel"

    # Test AccessDenied
    with patch("psutil.Process", side_effect=psutil.AccessDenied(pid=999)):
        name = monitor._resolve_process_name(999)
        assert name == "system/elevated"

    # Test NoSuchProcess
    with patch("psutil.Process", side_effect=psutil.NoSuchProcess(pid=888)):
        name = monitor._resolve_process_name(888)
        assert name == "ephemeral/closed"

    # Test generic exception
    with patch("psutil.Process", side_effect=RuntimeError("unexpected")):
        name = monitor._resolve_process_name(777)
        assert name == "unknown"


def test_monitor_start_stop_lifecycle():
    """Verify background monitor thread starts and terminates cleanly."""
    engine = NetworkPolicyEngine(DEFAULT_POLICY_PATH)
    ring_buffer = ConnectionRingBuffer(capacity=50)
    monitor = NetworkMonitor(policy_engine=engine, ring_buffer=ring_buffer, poll_interval=0.05)

    assert not monitor.is_running
    monitor.start()
    assert monitor.is_running
    monitor.stop()
    assert not monitor.is_running
