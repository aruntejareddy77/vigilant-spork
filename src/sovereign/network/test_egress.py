"""
src/sovereign/network/test_egress.py
Multi-protocol synthetic egress probe harness for proving air-gap zero-egress enforcement.
"""
import logging
from pathlib import Path
import socket
import time
from typing import List, Optional

from sovereign.audit.ledger import AuditLedger
from sovereign.network.models import ProbeResult
from sovereign.network.policy import NetworkPolicyEngine

logger = logging.getLogger("sovereign.network.egress")


class EgressTestHarness:
    """
    Automated multi-protocol synthetic probe suite.
    Attempts outbound network communication across DNS (53), HTTP (80),
    HTTPS (443), NTP (123), and raw TCP sockets to verify default-deny isolation.
    """

    def __init__(
        self,
        policy_engine: Optional[NetworkPolicyEngine] = None,
        audit_ledger: Optional[AuditLedger] = None,
    ):
        self.policy_engine = policy_engine
        self.audit_ledger = audit_ledger

    def _record_audit_denial(self, protocol: str, host: str, port: int, reason: str) -> None:
        if self.audit_ledger is not None:
            try:
                self.audit_ledger.append_event(
                    session_id="egress-test",
                    event_type="SECURITY_ALERT_NETWORK_DENY",
                    actor_role="egress-test-harness",
                    payload={
                        "protocol": protocol,
                        "target_host": host,
                        "target_port": port,
                        "test_harness_status": "BLOCKED",
                        "policy_reason": reason,
                    },
                )
            except Exception as exc:
                logger.error(f"Failed to record egress test denial to audit ledger: {exc}")

    def probe_dns(self, host: str = "8.8.8.8", port: int = 53, timeout: float = 1.0) -> ProbeResult:
        """Attempts a DNS query over UDP to an external resolver."""
        start = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        # Standard minimal DNS query header for root "."
        dns_query = b"\xaa\xbb\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x01"

        try:
            sock.sendto(dns_query, (host, port))
            data, _ = sock.recvfrom(512)
            latency = (time.perf_counter() - start) * 1000
            sock.close()
            return ProbeResult(
                protocol="dns_udp",
                target_host=host,
                target_port=port,
                outcome="LEAKED",
                reason=f"Received {len(data)} bytes from external DNS",
                latency_ms=round(latency, 2),
            )
        except (socket.timeout, TimeoutError):
            latency = (time.perf_counter() - start) * 1000
            sock.close()
            self._record_audit_denial("dns_udp", host, port, "timeout_air_gap_blocked")
            return ProbeResult(
                protocol="dns_udp",
                target_host=host,
                target_port=port,
                outcome="BLOCKED",
                reason="Connection timed out (air-gap blocked)",
                latency_ms=round(latency, 2),
            )
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            sock.close()
            self._record_audit_denial("dns_udp", host, port, str(exc))
            return ProbeResult(
                protocol="dns_udp",
                target_host=host,
                target_port=port,
                outcome="BLOCKED",
                reason=f"Socket error ({type(exc).__name__})",
                latency_ms=round(latency, 2),
            )

    def probe_http(self, host: str = "1.1.1.1", port: int = 80, timeout: float = 1.0) -> ProbeResult:
        """Attempts a plain HTTP TCP connection to an external IP."""
        return self._probe_tcp_generic(protocol="http_tcp", host=host, port=port, timeout=timeout)

    def probe_https(self, host: str = "1.1.1.1", port: int = 443, timeout: float = 1.0) -> ProbeResult:
        """Attempts an HTTPS TCP connection to an external IP."""
        return self._probe_tcp_generic(protocol="https_tcp", host=host, port=port, timeout=timeout)

    def probe_raw_socket(self, host: str = "8.8.4.4", port: int = 9999, timeout: float = 1.0) -> ProbeResult:
        """Attempts a raw TCP connection to an arbitrary public IP and port."""
        return self._probe_tcp_generic(protocol="raw_tcp", host=host, port=port, timeout=timeout)

    def _probe_tcp_generic(self, protocol: str, host: str, port: int, timeout: float) -> ProbeResult:
        start = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        try:
            sock.connect((host, port))
            latency = (time.perf_counter() - start) * 1000
            sock.close()
            return ProbeResult(
                protocol=protocol,
                target_host=host,
                target_port=port,
                outcome="LEAKED",
                reason="TCP connection successfully established",
                latency_ms=round(latency, 2),
            )
        except (socket.timeout, TimeoutError):
            latency = (time.perf_counter() - start) * 1000
            sock.close()
            self._record_audit_denial(protocol, host, port, "timeout_air_gap_blocked")
            return ProbeResult(
                protocol=protocol,
                target_host=host,
                target_port=port,
                outcome="BLOCKED",
                reason="Connection timed out (air-gap blocked)",
                latency_ms=round(latency, 2),
            )
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            sock.close()
            self._record_audit_denial(protocol, host, port, str(exc))
            return ProbeResult(
                protocol=protocol,
                target_host=host,
                target_port=port,
                outcome="BLOCKED",
                reason=f"Socket error ({type(exc).__name__})",
                latency_ms=round(latency, 2),
            )

    def probe_ntp(self, host: str = "129.6.15.28", port: int = 123, timeout: float = 1.0) -> ProbeResult:
        """Attempts an NTP timestamp synchronization packet over UDP (NIST IP 129.6.15.28)."""
        start = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        ntp_packet = b"\x1b" + 47 * b"\0"

        try:
            sock.sendto(ntp_packet, (host, port))
            data, _ = sock.recvfrom(48)
            latency = (time.perf_counter() - start) * 1000
            sock.close()
            return ProbeResult(
                protocol="ntp_udp",
                target_host=host,
                target_port=port,
                outcome="LEAKED",
                reason=f"Received {len(data)} byte NTP response from external time server",
                latency_ms=round(latency, 2),
            )
        except (socket.timeout, TimeoutError):
            latency = (time.perf_counter() - start) * 1000
            sock.close()
            self._record_audit_denial("ntp_udp", host, port, "timeout_air_gap_blocked")
            return ProbeResult(
                protocol="ntp_udp",
                target_host=host,
                target_port=port,
                outcome="BLOCKED",
                reason="NTP request timed out (air-gap blocked)",
                latency_ms=round(latency, 2),
            )
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            sock.close()
            self._record_audit_denial("ntp_udp", host, port, str(exc))
            return ProbeResult(
                protocol="ntp_udp",
                target_host=host,
                target_port=port,
                outcome="BLOCKED",
                reason=f"Socket error ({type(exc).__name__})",
                latency_ms=round(latency, 2),
            )

    def run_all_probes(self, timeout: float = 1.0) -> List[ProbeResult]:
        """Runs the complete suite of synthetic egress probes across all protocols."""
        return [
            self.probe_dns(host="8.8.8.8", port=53, timeout=timeout),
            self.probe_dns(host="1.1.1.1", port=53, timeout=timeout),
            self.probe_http(host="1.1.1.1", port=80, timeout=timeout),
            self.probe_https(host="1.1.1.1", port=443, timeout=timeout),
            self.probe_ntp(host="129.6.15.28", port=123, timeout=timeout),
            self.probe_raw_socket(host="8.8.4.4", port=9999, timeout=timeout),
        ]


def run_egress_probes(
    policy_engine: Optional[NetworkPolicyEngine] = None,
    audit_ledger: Optional[AuditLedger] = None,
    timeout: float = 1.0,
) -> List[ProbeResult]:
    """Convenience entry point executing the full synthetic egress probe suite."""
    harness = EgressTestHarness(policy_engine=policy_engine, audit_ledger=audit_ledger)
    return harness.run_all_probes(timeout=timeout)
