"""
tests/test_network/test_ring_buffer.py
Unit tests for thread-safe circular in-memory telemetry ring buffer.
"""
import concurrent.futures
from sovereign.network.models import NetworkEvent
from sovereign.network.ring_buffer import ConnectionRingBuffer


def test_ring_buffer_append_and_counts():
    """Verify appending events increments total, allow, and deny counts."""
    buf = ConnectionRingBuffer(capacity=100)

    e1 = NetworkEvent(
        timestamp_iso="2026-09-10T10:00:00Z",
        protocol="tcp",
        local_address="127.0.0.1:8000",
        remote_address="127.0.0.1:54321",
        pid=1234,
        process_name="python.exe",
        verdict="ALLOW",
        reason="loopback_allowed",
    )
    e2 = NetworkEvent(
        timestamp_iso="2026-09-10T10:00:01Z",
        protocol="tcp",
        local_address="192.168.1.10:44321",
        remote_address="8.8.8.8:53",
        pid=5678,
        process_name="curl.exe",
        verdict="DENY",
        reason="port_53_strictly_denied",
    )

    buf.append(e1)
    buf.append(e2)

    assert buf.count() == 2
    assert buf.total_events == 2
    assert buf.allowed_count == 1
    assert buf.denied_count == 1

    recent = buf.get_recent(limit=10)
    assert len(recent) == 2
    # newest first
    assert recent[0].pid == 5678
    assert recent[1].pid == 1234


def test_circular_eviction_at_capacity():
    """Verify buffer caps at specified capacity and evicts oldest entries."""
    capacity = 100
    buf = ConnectionRingBuffer(capacity=capacity)

    # Insert 150 items
    for i in range(150):
        buf.append(
            NetworkEvent(
                timestamp_iso=f"2026-09-10T10:{i % 60:02d}:00Z",
                protocol="tcp",
                local_address="127.0.0.1:80",
                remote_address=f"127.0.0.1:{10000 + i}",
                pid=i,
                process_name="test",
                verdict="ALLOW",
                reason="ok",
            )
        )

    assert buf.count() == capacity
    assert buf.total_events == 150

    recent = buf.get_recent(limit=capacity)
    # The newest element should be pid 149
    assert recent[0].pid == 149
    # The oldest surviving element should be pid 50 (0..49 were evicted)
    assert recent[-1].pid == 50


def test_concurrent_ring_buffer_access():
    """Verify thread safety under heavy concurrent appends."""
    buf = ConnectionRingBuffer(capacity=1000)
    total_appends = 500

    def worker(idx: int):
        buf.append(
            NetworkEvent(
                timestamp_iso="2026-09-10T10:00:00Z",
                protocol="tcp",
                local_address="127.0.0.1:80",
                remote_address=f"10.0.0.{idx % 255}:80",
                pid=idx,
                process_name="worker",
                verdict="ALLOW" if idx % 2 == 0 else "DENY",
                reason="test",
            )
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, i) for i in range(total_appends)]
        concurrent.futures.wait(futures)

    assert buf.total_events == total_appends
    assert buf.count() == total_appends
    assert buf.allowed_count == 250
    assert buf.denied_count == 250

    snap = buf.get_snapshot(limit=50)
    assert snap.total_events == total_appends
    assert len(snap.recent_events) == 50
