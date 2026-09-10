"""
src/sovereign/network/policy.py
Cross-Platform Declarative Network Policy Evaluator using Python's ipaddress module.
"""
import ipaddress
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union
import yaml

from sovereign.network.models import PolicyConfig


class NetworkPolicyEngine:
    """
    Evaluates socket connections against a declarative network policy.
    Uses native ipaddress subnet containment math to prevent regex parsing errors.
    """

    def __init__(self, policy: Union[str, Path, Dict[str, Any], PolicyConfig]):
        if isinstance(policy, PolicyConfig):
            raw_dict = policy.model_dump()
        elif isinstance(policy, (str, Path)):
            p_path = Path(policy)
            with open(p_path, "r", encoding="utf-8") as f:
                raw_dict = yaml.safe_load(f) or {}
        elif isinstance(policy, dict):
            raw_dict = policy
        else:
            raw_dict = {}

        self.policy_name = raw_dict.get("policy_name", "sovereign_default_deny")
        self.default_action = raw_dict.get("default_action", "DENY")
        self.denied_ports: List[int] = [int(p) for p in raw_dict.get("denied_ports", [53])]

        # Parse loopback CIDRs
        self.allowed_loopback: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []
        for cidr_str in raw_dict.get("allowed_loopback", ["127.0.0.0/8", "::1/128"]):
            try:
                self.allowed_loopback.append(ipaddress.ip_network(cidr_str))
            except ValueError:
                pass

        # Parse intranet CIDRs
        self.allowed_intranet: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []
        for cidr_str in raw_dict.get("allowed_intranet_cidrs", []):
            try:
                self.allowed_intranet.append(ipaddress.ip_network(cidr_str))
            except ValueError:
                pass

    def evaluate_connection(self, remote_ip: str, remote_port: int) -> Tuple[str, str]:
        """
        Evaluates a remote destination IP and port against the active network policy.

        Returns:
            Tuple of (verdict: "ALLOW" | "DENY", reason: str)
        """
        clean_ip = (remote_ip or "").strip()
        if not clean_ip or clean_ip in ("0.0.0.0", "::") or (clean_ip == "" and remote_port == 0):
            return "ALLOW", "local_listening"

        try:
            ip = ipaddress.ip_address(clean_ip)
        except ValueError:
            return "DENY", "invalid_ip_format"

        # Check explicitly denied ports (e.g. port 53 DNS)
        if remote_port in self.denied_ports:
            return "DENY", f"port_{remote_port}_strictly_denied"

        # Check loopback containment
        if ip.is_loopback or any(ip in net for net in self.allowed_loopback):
            return "ALLOW", "loopback_allowed"

        # Check configured intranet CIDRs
        if any(ip in net for net in self.allowed_intranet):
            return "ALLOW", "intranet_allowed"

        # Default fallback: reject all public internet egress
        return "DENY", "public_egress_default_deny"
