"""
tests/test_server/conftest.py
Shared fixtures for the server test suite.
"""
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from sovereign.audit.ledger import AuditLedger
from sovereign.network.policy import NetworkPolicyEngine
from sovereign.server.config import ServerConfig


@pytest.fixture
def policy_engine() -> NetworkPolicyEngine:
    """Create a NetworkPolicyEngine with standard default-deny policy."""
    return NetworkPolicyEngine({
        "policy_name": "test_default_deny",
        "allowed_loopback": ["127.0.0.0/8", "::1/128"],
        "allowed_intranet_cidrs": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"],
        "denied_ports": [53],
        "default_action": "DENY",
    })


@pytest.fixture
def server_config() -> ServerConfig:
    """Create a default ServerConfig."""
    return ServerConfig()


@pytest.fixture
def tmp_ledger(tmp_path: Path) -> AuditLedger:
    """Create a temporary AuditLedger for RBAC violation testing."""
    ledger_path = tmp_path / "test_audit_ledger.jsonl"
    return AuditLedger(ledger_path)


@pytest.fixture
def secret_key() -> str:
    """Test secret key for token operations."""
    return "test-secret-key-for-sovereign-workbench"
