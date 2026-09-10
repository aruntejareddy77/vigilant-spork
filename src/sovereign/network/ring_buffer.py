"""
src/sovereign/network/ring_buffer.py
Thread-safe circular in-memory telemetry ring buffer (10,000 capacity).
"""
from collections import deque
import threading
from typing import List, Optional

from sovereign.network.models import NetworkEvent, TelemetrySnapshot


class ConnectionRingBuffer:
    """
    Thread-safe circular ring buffer wrapping collections.deque(maxlen=capacity).
    Holds high-frequency socket connection telemetry in memory with constant-time
    appends and automatic FIFO eviction.
    """

    def __init__(self, capacity: int = 10000):
        self.capacity = capacity
        self._buffer: deque[NetworkEvent] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self.total_events = 0
        self.allowed_count = 0
        self.denied_count = 0

    def append(self, event: NetworkEvent) -> None:
        """Appends a new NetworkEvent, automatically evicting oldest item if full."""
        with self._lock:
            self._buffer.append(event)
            self.total_events += 1
            if event.verdict == "ALLOW":
                self.allowed_count += 1
            elif event.verdict == "DENY":
                self.denied_count += 1

    def get_recent(self, limit: int = 100) -> List[NetworkEvent]:
        """Returns the most recent events up to limit (newest first)."""
        with self._lock:
            # Convert to list and slice from tail
            items = list(self._buffer)
            return items[-limit:][::-1]

    def get_snapshot(self, limit: int = 100) -> TelemetrySnapshot:
        """Returns a snapshot of current telemetry state and metrics."""
        with self._lock:
            items = list(self._buffer)[-limit:][::-1]
            return TelemetrySnapshot(
                total_events=self.total_events,
                allowed_count=self.allowed_count,
                denied_count=self.denied_count,
                capacity=self.capacity,
                recent_events=items,
            )

    def count(self) -> int:
        """Returns current number of buffered events."""
        with self._lock:
            return len(self._buffer)

    def clear(self) -> None:
        """Resets the ring buffer and all counters."""
        with self._lock:
            self._buffer.clear()
            self.total_events = 0
            self.allowed_count = 0
            self.denied_count = 0
