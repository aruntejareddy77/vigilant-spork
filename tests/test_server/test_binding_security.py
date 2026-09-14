"""
tests/test_server/test_binding_security.py
Tests for server binding security guard and HostHeaderMiddleware.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sovereign.network.policy import NetworkPolicyEngine
from sovereign.server.config import (
    BindingSecurityError,
    HostHeaderMiddleware,
    ServerConfig,
    validate_server_binding,
)


# =============================================================================
# Binding Security Guard Tests
# =============================================================================


class TestValidateServerBinding:
    """Tests for the validate_server_binding function."""

    def _make_engine(self):
        return NetworkPolicyEngine({
            "policy_name": "test_policy",
            "allowed_loopback": ["127.0.0.0/8", "::1/128"],
            "allowed_intranet_cidrs": [
                "10.0.0.0/8",
                "172.16.0.0/12",
                "192.168.0.0/16",
            ],
            "denied_ports": [53],
            "default_action": "DENY",
        })

    def test_rejects_all_interfaces_ipv4(self):
        """0.0.0.0 must be rejected — exposes to all interfaces."""
        with pytest.raises(BindingSecurityError, match="0.0.0.0"):
            validate_server_binding("0.0.0.0")

    def test_rejects_all_interfaces_ipv6(self):
        """:: must be rejected — IPv6 all-interfaces."""
        with pytest.raises(BindingSecurityError, match="::"):
            validate_server_binding("::")

    def test_rejects_empty_string(self):
        """Empty string must be rejected."""
        with pytest.raises(BindingSecurityError):
            validate_server_binding("")

    def test_allows_loopback_ipv4(self):
        """127.0.0.1 should always be allowed."""
        validate_server_binding("127.0.0.1")  # Should not raise

    def test_allows_loopback_ipv6(self):
        """::1 should always be allowed."""
        validate_server_binding("::1")  # Should not raise

    def test_allows_localhost(self):
        """'localhost' should always be allowed."""
        validate_server_binding("localhost")  # Should not raise

    def test_allows_intranet_ip_192(self):
        """IP within 192.168.0.0/16 should be allowed when policy permits."""
        engine = self._make_engine()
        validate_server_binding("192.168.1.10", policy_engine=engine)

    def test_allows_intranet_ip_10(self):
        """IP within 10.0.0.0/8 should be allowed when policy permits."""
        engine = self._make_engine()
        validate_server_binding("10.0.5.20", policy_engine=engine)

    def test_allows_intranet_ip_172(self):
        """IP within 172.16.0.0/12 should be allowed when policy permits."""
        engine = self._make_engine()
        validate_server_binding("172.16.0.1", policy_engine=engine)

    def test_rejects_public_ip_google_dns(self):
        """8.8.8.8 is a public IP and must be rejected."""
        engine = self._make_engine()
        with pytest.raises(BindingSecurityError, match="not permitted"):
            validate_server_binding("8.8.8.8", policy_engine=engine)

    def test_rejects_public_ip_example(self):
        """93.184.216.34 (example.com) must be rejected."""
        engine = self._make_engine()
        with pytest.raises(BindingSecurityError, match="not permitted"):
            validate_server_binding("93.184.216.34", policy_engine=engine)

    def test_rejects_nonresolvable_hostname(self):
        """Non-resolvable, non-loopback hostnames must be rejected."""
        engine = self._make_engine()
        with pytest.raises(BindingSecurityError):
            validate_server_binding(
                "this-host-definitely-does-not-exist-xyzzy.invalid",
                policy_engine=engine,
            )


class TestServerConfig:
    """Tests for ServerConfig Pydantic model."""

    def test_default_config(self):
        """Default config should bind to 127.0.0.1:8000."""
        config = ServerConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 8000

    def test_validate_binding_passes_for_localhost(self):
        """Default config should pass binding validation."""
        config = ServerConfig()
        config.validate_binding()  # Should not raise

    def test_validate_binding_fails_for_unsafe_host(self):
        """Config with 0.0.0.0 should fail binding validation."""
        config = ServerConfig(host="0.0.0.0")
        with pytest.raises(BindingSecurityError):
            config.validate_binding()


# =============================================================================
# HostHeaderMiddleware Tests
# =============================================================================


class TestHostHeaderMiddleware:
    """Tests for DNS rebinding protection middleware."""

    def _create_app(self, allowed_hosts=None):
        app = FastAPI()
        app.add_middleware(HostHeaderMiddleware, allowed_hosts=allowed_hosts)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        return app

    def test_accepts_localhost_with_port(self):
        """Host: localhost:8000 should be accepted."""
        app = self._create_app()
        client = TestClient(app)
        response = client.get("/test", headers={"host": "localhost:8000"})
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_accepts_localhost_without_port(self):
        """Host: localhost should be accepted."""
        app = self._create_app()
        client = TestClient(app)
        response = client.get("/test", headers={"host": "localhost"})
        assert response.status_code == 200

    def test_accepts_127_0_0_1_with_port(self):
        """Host: 127.0.0.1:8000 should be accepted."""
        app = self._create_app()
        client = TestClient(app)
        response = client.get("/test", headers={"host": "127.0.0.1:8000"})
        assert response.status_code == 200

    def test_rejects_attacker_com(self):
        """Host: attacker.com must be rejected with HTTP 400."""
        app = self._create_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test", headers={"host": "attacker.com"})
        assert response.status_code == 400
        assert "Invalid Host header" in response.json()["detail"]

    def test_rejects_evil_internal_corp(self):
        """Host: evil.internal.corp must be rejected with HTTP 400."""
        app = self._create_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test", headers={"host": "evil.internal.corp"})
        assert response.status_code == 400

    def test_custom_allowed_host(self):
        """Custom allowed hosts should be accepted."""
        app = self._create_app(allowed_hosts=["myserver.local"])
        client = TestClient(app)
        response = client.get("/test", headers={"host": "myserver.local:8000"})
        assert response.status_code == 200

    def test_rejects_unlisted_custom_host(self):
        """Host not in the custom allowlist should be rejected."""
        app = self._create_app(allowed_hosts=["myserver.local"])
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test", headers={"host": "other.server"})
        assert response.status_code == 400
