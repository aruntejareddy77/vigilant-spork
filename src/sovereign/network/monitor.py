"""
src/sovereign/network/monitor.py
Cross-platform psutil socket connection polling worker and audit escalation sink.
"""
from datetime import datetime, timezone
import logging
from pathlib import Path
import socket
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import psutil

from sovereign.audit.ledger import AuditLedger
from sovereign.network.models import NetworkEvent
from sovereign.network.policy import NetworkPolicyEngine
from sovereign.network.ring_buffer import ConnectionRingBuffer

logger = logging.getLogger("sovereign.network.monitor")


class NetworkMonitor:
    """
    Background daemon worker that periodically scans active network sockets
    via psutil, evaluates endpoints against NetworkPolicyEngine, records them into
    ConnectionRingBuffer, and escalates DENY events directly into the AuditLedger.
    """

    def __init__(
        self,
        policy_engine: NetworkPolicyEngine,
        ring_buffer: ConnectionRingBuffer,
        audit_ledger: Optional[AuditLedger] = None,
        poll_interval: float = 0.25,
        event_callback: Optional[Callable[[NetworkEvent], None]] = None,
    ):
        self.policy_engine = policy_engine
        self.ring_buffer = ring_buffer
        self.audit_ledger = audit_ledger
        self.poll_interval = poll_interval
        self.event_callback = event_callback

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._pid_cache: Dict[int, str] = {}
        self._cache_lock = threading.Lock()

    def _resolve_process_name(self, pid: Optional[int]) -> str:
        """Resolves process name defensively without crashing on unprivileged sockets."""
        if not pid or pid < 0:
            return "system/kernel"

        with self._cache_lock:
            if pid in self._pid_cache:
                return self._pid_cache[pid]

        try:
            proc = psutil.Process(pid)
            name = proc.name()
        except psutil.AccessDenied:
            name = "system/elevated"
        except psutil.NoSuchProcess:
            name = "ephemeral/closed"
        except Exception:
            name = "unknown"

        with self._cache_lock:
            self._pid_cache[pid] = name
            if len(self._pid_cache) > 2000:
                self._pid_cache.clear()

        return name

    def poll_once(self) -> List[NetworkEvent]:
        """
        Executes a single socket scan cycle.
        Returns the list of NetworkEvents captured in this cycle.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        events_this_poll: List[NetworkEvent] = []

        try:
            connections = psutil.net_connections(kind="inet")
        except Exception as exc:
            logger.warning(f"Error querying psutil net_connections: {exc}")
            return []

        for conn in connections:
            proto = "tcp" if conn.type == socket.SOCK_STREAM else "udp"

            local_addr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
            remote_ip = conn.raddr.ip if conn.raddr else ""
            remote_port = conn.raddr.port if conn.raddr else 0
            remote_addr = f"{remote_ip}:{remote_port}" if conn.raddr else ""

            verdict, reason = self.policy_engine.evaluate_connection(remote_ip, remote_port)
            proc_name = self._resolve_process_name(conn.pid)

            event = NetworkEvent(
                timestamp_iso=now_iso,
                protocol=proto,
                local_address=local_addr,
                remote_address=remote_addr,
                pid=conn.pid,
                process_name=proc_name,
                verdict=verdict,
                reason=reason,
            )

            self.ring_buffer.append(event)
            events_this_poll.append(event)

            # Escalate any DENY event directly to the cryptographic audit ledger
            if verdict == "DENY" and self.audit_ledger is not None:
                try:
                    self.audit_ledger.append_event(
                        session_id="network-telemetry",
                        event_type="SECURITY_ALERT_NETWORK_DENY",
                        actor_role="network-monitor",
                        payload={
                            "pid": conn.pid,
                            "process_name": proc_name,
                            "local_address": local_addr,
                            "remote_address": remote_addr,
                            "remote_ip": remote_ip,
                            "remote_port": remote_port,
                            "protocol": proto,
                            "policy_reason": reason,
                        },
                    )
                except Exception as exc:
                    logger.error(f"Failed to sink DENY event to audit ledger: {exc}")

            if self.event_callback:
                try:
                    self.event_callback(event)
                except Exception:
                    pass

        return events_this_poll

    def _worker_loop(self) -> None:
        while self._running:
            self.poll_once()
            time.sleep(self.poll_interval)

    def start(self) -> None:
        """Starts the socket monitoring worker thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="SovereignNetworkMonitor")
        self._thread.start()

    def stop(self) -> None:
        """Stops the socket monitoring worker thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    @property
    def is_running(self) -> bool:
        return self._running
