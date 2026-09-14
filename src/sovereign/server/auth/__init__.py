"""
src/sovereign/server/auth/__init__.py
Authentication and RBAC package for the Sovereign server.
"""
from sovereign.server.auth.tokens import create_access_token, verify_access_token
from sovereign.server.auth.rbac import RBACGuard, require_role

__all__ = [
    "create_access_token",
    "verify_access_token",
    "RBACGuard",
    "require_role",
]
