"""
tests/test_server/test_rbac_middleware.py
Tests for 3-Tier RBAC middleware and cryptographic token system.
"""
import json
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from sovereign.audit.ledger import AuditLedger
from sovereign.server.auth.rbac import RBACGuard, require_role
from sovereign.server.auth.tokens import create_access_token, verify_access_token
from sovereign.tools.schemas import UserRole


# =============================================================================
# Token Creation & Verification Tests
# =============================================================================


class TestTokens:
    """Tests for token creation and verification roundtrip."""

    def test_create_admin_token(self, secret_key):
        """Admin token should have sovg_admin_ prefix."""
        token = create_access_token(UserRole.ADMIN, secret_key)
        assert token.startswith("sovg_admin_")

    def test_create_engineer_token(self, secret_key):
        """Engineer token should have sovg_eng_ prefix."""
        token = create_access_token(UserRole.ENGINEER, secret_key)
        assert token.startswith("sovg_eng_")

    def test_create_auditor_token(self, secret_key):
        """Auditor token should have sovg_aud_ prefix."""
        token = create_access_token(UserRole.AUDITOR, secret_key)
        assert token.startswith("sovg_aud_")

    def test_verify_admin_token_roundtrip(self, secret_key):
        """Created admin token should verify successfully."""
        token = create_access_token(UserRole.ADMIN, secret_key)
        is_valid, role, subject = verify_access_token(token, secret_key)
        assert is_valid is True
        assert role == UserRole.ADMIN
        assert subject == "operator"

    def test_verify_engineer_token_roundtrip(self, secret_key):
        """Created engineer token should verify successfully."""
        token = create_access_token(UserRole.ENGINEER, secret_key)
        is_valid, role, subject = verify_access_token(token, secret_key)
        assert is_valid is True
        assert role == UserRole.ENGINEER

    def test_verify_auditor_token_roundtrip(self, secret_key):
        """Created auditor token should verify successfully."""
        token = create_access_token(UserRole.AUDITOR, secret_key)
        is_valid, role, subject = verify_access_token(token, secret_key)
        assert is_valid is True
        assert role == UserRole.AUDITOR

    def test_invalid_token(self, secret_key):
        """Invalid token should fail verification."""
        is_valid, role, subject = verify_access_token("invalid-token", secret_key)
        assert is_valid is False
        assert role is None

    def test_wrong_secret_key(self, secret_key):
        """Token verified with wrong secret should fail."""
        token = create_access_token(UserRole.ADMIN, secret_key)
        is_valid, role, subject = verify_access_token(token, "wrong-secret")
        assert is_valid is False

    def test_empty_token(self, secret_key):
        """Empty token should fail verification."""
        is_valid, role, subject = verify_access_token("", secret_key)
        assert is_valid is False

    def test_none_token(self, secret_key):
        """None token should fail verification."""
        is_valid, role, subject = verify_access_token(None, secret_key)
        assert is_valid is False


# =============================================================================
# RBAC Middleware Integration Tests
# =============================================================================


def _create_rbac_app(audit_ledger=None, secret_key="test-secret"):
    """Create a test FastAPI app with RBAC-protected routes."""
    app = FastAPI()
    app.state.secret_key = secret_key
    if audit_ledger:
        app.state.audit_ledger = audit_ledger

    @app.get(
        "/admin",
        dependencies=[Depends(require_role(UserRole.ADMIN, secret_key=secret_key))],
    )
    async def admin_endpoint():
        return {"access": "admin"}

    @app.get(
        "/engineer",
        dependencies=[Depends(require_role(UserRole.ENGINEER, secret_key=secret_key))],
    )
    async def engineer_endpoint():
        return {"access": "engineer"}

    @app.get(
        "/auditor",
        dependencies=[Depends(require_role(UserRole.AUDITOR, secret_key=secret_key))],
    )
    async def auditor_endpoint():
        return {"access": "auditor"}

    return app


class TestRBACMiddleware:
    """Tests for RBAC least-privilege enforcement via FastAPI dependency injection."""

    def test_admin_accesses_admin(self, secret_key):
        """Admin should access Admin endpoint (200 OK)."""
        app = _create_rbac_app(secret_key=secret_key)
        client = TestClient(app)
        token = create_access_token(UserRole.ADMIN, secret_key)
        response = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["access"] == "admin"

    def test_admin_accesses_engineer(self, secret_key):
        """Admin should access Engineer endpoint (200 OK)."""
        app = _create_rbac_app(secret_key=secret_key)
        client = TestClient(app)
        token = create_access_token(UserRole.ADMIN, secret_key)
        response = client.get(
            "/engineer", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_admin_accesses_auditor(self, secret_key):
        """Admin should access Auditor endpoint (200 OK)."""
        app = _create_rbac_app(secret_key=secret_key)
        client = TestClient(app)
        token = create_access_token(UserRole.ADMIN, secret_key)
        response = client.get(
            "/auditor", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_engineer_accesses_engineer(self, secret_key):
        """Engineer should access Engineer endpoint (200 OK)."""
        app = _create_rbac_app(secret_key=secret_key)
        client = TestClient(app)
        token = create_access_token(UserRole.ENGINEER, secret_key)
        response = client.get(
            "/engineer", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_engineer_accesses_auditor(self, secret_key):
        """Engineer should access Auditor endpoint (200 OK)."""
        app = _create_rbac_app(secret_key=secret_key)
        client = TestClient(app)
        token = create_access_token(UserRole.ENGINEER, secret_key)
        response = client.get(
            "/auditor", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_engineer_denied_admin(self, secret_key):
        """Engineer should be denied Admin endpoint (403 Forbidden)."""
        app = _create_rbac_app(secret_key=secret_key)
        client = TestClient(app)
        token = create_access_token(UserRole.ENGINEER, secret_key)
        response = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

    def test_auditor_accesses_auditor(self, secret_key):
        """Auditor should access Auditor endpoint (200 OK)."""
        app = _create_rbac_app(secret_key=secret_key)
        client = TestClient(app)
        token = create_access_token(UserRole.AUDITOR, secret_key)
        response = client.get(
            "/auditor", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_auditor_denied_engineer(self, secret_key):
        """Auditor should be denied Engineer endpoint (403 Forbidden)."""
        app = _create_rbac_app(secret_key=secret_key)
        client = TestClient(app)
        token = create_access_token(UserRole.AUDITOR, secret_key)
        response = client.get(
            "/engineer", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

    def test_auditor_denied_admin(self, secret_key):
        """Auditor should be denied Admin endpoint (403 Forbidden)."""
        app = _create_rbac_app(secret_key=secret_key)
        client = TestClient(app)
        token = create_access_token(UserRole.AUDITOR, secret_key)
        response = client.get("/admin", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    def test_x_sovereign_role_header_fallback(self, secret_key):
        """X-Sovereign-Role header should work as fallback auth."""
        app = _create_rbac_app(secret_key=secret_key)
        client = TestClient(app)
        response = client.get(
            "/engineer", headers={"X-Sovereign-Role": "engineer"}
        )
        assert response.status_code == 200

    def test_unauthenticated_defaults_to_auditor(self, secret_key):
        """Unauthenticated requests should default to Auditor role."""
        app = _create_rbac_app(secret_key=secret_key)
        client = TestClient(app)
        # No auth header — should default to Auditor and access /auditor
        response = client.get("/auditor")
        assert response.status_code == 200
        # But denied from /engineer
        response = client.get("/engineer")
        assert response.status_code == 403


class TestRBACViolationAudit:
    """Tests that RBAC violations are logged to the AuditLedger."""

    def test_auditor_violation_logged_to_ledger(self, secret_key, tmp_ledger):
        """Auditor calling an Engineer endpoint should log SECURITY_ALERT_RBAC_VIOLATION."""
        app = _create_rbac_app(audit_ledger=tmp_ledger, secret_key=secret_key)
        app.state.audit_ledger = tmp_ledger
        client = TestClient(app)
        token = create_access_token(UserRole.AUDITOR, secret_key)

        # This should be denied (403) and logged
        response = client.get(
            "/engineer", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

        # Verify the ledger contains the violation event
        assert tmp_ledger.ledger_path.exists()
        with open(tmp_ledger.ledger_path, "r") as f:
            lines = [line.strip() for line in f if line.strip()]

        assert len(lines) >= 1
        event = json.loads(lines[-1])
        assert event["event_type"] == "SECURITY_ALERT_RBAC_VIOLATION"
        assert event["actor_role"] == "auditor"
        assert event["payload"]["required_role"] == "engineer"
        assert event["payload"]["user_role"] == "auditor"
        # Verify hash chain is intact (entry_hash is present)
        assert "entry_hash" in event
        assert len(event["entry_hash"]) == 64  # SHA-256 hex digest
