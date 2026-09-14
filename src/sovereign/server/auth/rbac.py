"""
src/sovereign/server/auth/rbac.py
3-Tier RBAC guard and dependency injection for FastAPI routes.

Uses the existing UserRole enum and has_clearance() from sovereign.tools.schemas.
Logs SECURITY_ALERT_RBAC_VIOLATION events to the AuditLedger on access denial.
"""
import logging
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sovereign.audit.ledger import AuditLedger
from sovereign.server.auth.tokens import verify_access_token
from sovereign.tools.schemas import UserRole, has_clearance

logger = logging.getLogger("sovereign.server.auth.rbac")

# Optional bearer token extraction (auto_error=False so missing token doesn't 401)
_bearer_scheme = HTTPBearer(auto_error=False)


class RBACGuard:
    """
    FastAPI dependency callable that enforces minimum role clearance.

    Usage in routes:
        @router.post("/api/tasks", dependencies=[Depends(require_role(UserRole.ENGINEER))])

    Resolves user role from:
      1. Authorization: Bearer <token> header (cryptographic verification)
      2. X-Sovereign-Role: <role> header (dev/kiosk mode fallback)
      3. Defaults to UserRole.AUDITOR if unauthenticated
    """

    def __init__(
        self,
        min_role: UserRole,
        audit_ledger: Optional[AuditLedger] = None,
        secret_key: Optional[str] = None,
    ):
        self.min_role = min_role
        self.audit_ledger = audit_ledger
        self.secret_key = secret_key or "sovereign-dev-secret-key-change-in-production"

    async def __call__(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    ) -> UserRole:
        """Resolve user role and enforce clearance check."""
        user_role = self._resolve_role(request, credentials)

        if not has_clearance(user_role, self.min_role):
            # Log RBAC violation to the audit ledger
            self._log_violation(request, user_role)

            raise HTTPException(
                status_code=403,
                detail=(
                    f"Access denied: role '{user_role.value}' does not have "
                    f"required clearance '{self.min_role.value}'."
                ),
            )

        return user_role

    def _resolve_role(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials],
    ) -> UserRole:
        """Extract and verify user role from request headers."""
        # 1. Try Bearer token
        if credentials and credentials.credentials:
            token = credentials.credentials
            # Check app state for secret key override
            app_secret = getattr(request.app.state, "secret_key", self.secret_key)
            is_valid, role, _ = verify_access_token(token, app_secret)
            if is_valid and role is not None:
                return role

        # 2. Try X-Sovereign-Role header (dev/kiosk fallback)
        role_header = request.headers.get("x-sovereign-role", "").strip().lower()
        if role_header:
            try:
                return UserRole(role_header)
            except ValueError:
                pass

        # 3. Default to Auditor (least privilege)
        return UserRole.AUDITOR

    def _log_violation(self, request: Request, user_role: UserRole) -> None:
        """Log an RBAC violation event to the audit ledger."""
        # Try to get the audit ledger from the app state if not provided at init
        ledger = self.audit_ledger
        if ledger is None:
            ledger = getattr(request.app.state, "audit_ledger", None)

        if ledger is not None:
            try:
                client_ip = request.client.host if request.client else "unknown"
                ledger.append_event(
                    session_id="sec-audit-violation",
                    event_type="SECURITY_ALERT_RBAC_VIOLATION",
                    actor_role=user_role.value,
                    payload={
                        "attempted_action": f"{request.method} {request.url.path}",
                        "required_role": self.min_role.value,
                        "user_role": user_role.value,
                        "client_ip": client_ip,
                    },
                )
            except Exception as exc:
                logger.error(f"Failed to log RBAC violation: {exc}")


def require_role(
    min_role: UserRole,
    audit_ledger: Optional[AuditLedger] = None,
    secret_key: Optional[str] = None,
) -> Callable:
    """
    Factory function for FastAPI route dependency injection.

    Returns a dependency callable that enforces the minimum role clearance.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role(UserRole.ADMIN))])
    """
    return RBACGuard(
        min_role=min_role,
        audit_ledger=audit_ledger,
        secret_key=secret_key,
    )
