"""
src/sovereign/sdk/exceptions.py
Exception hierarchy for the Sovereign Python SDK.
"""
from typing import Any, Optional


class SovereignError(Exception):
    """Base exception for all Sovereign SDK errors."""
    pass


class SovereignAPIError(SovereignError):
    """Encapsulates HTTP status codes and error messages returned by the Workbench API."""

    def __init__(self, status_code: int, message: str, detail: Optional[Any] = None):
        super().__init__(f"API Error {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.detail = detail


class RBACPermissionError(SovereignError):
    """Raised when the active user role lacks required clearance for an operation."""
    pass


class SovereignConnectionError(SovereignError):
    """Raised when the Sovereign Workbench API is unreachable."""
    pass


# Convenience alias
ConnectionError = SovereignConnectionError
