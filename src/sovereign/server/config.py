"""
src/sovereign/server/config.py
Server binding security guard, HostHeaderMiddleware, and configuration.

Fail-closed validation ensures the server never binds to 0.0.0.0, ::, or
unauthorized public IPs. Only loopback and declared intranet CIDRs from
network_policy.yaml are permitted.
"""
import ipaddress
import socket
from typing import List, Optional, Union

from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from sovereign.network.policy import NetworkPolicyEngine


class BindingSecurityError(Exception):
    """Raised when an attempt is made to bind to an unauthorized network interface."""
    pass


def validate_server_binding(
    host: str,
    policy_engine: Optional[NetworkPolicyEngine] = None,
) -> None:
    """
    Validates that the specified host address is safe for binding.

    Immediately raises BindingSecurityError if host is:
      - "0.0.0.0" (all IPv4 interfaces)
      - "::" (all IPv6 interfaces)
      - "" (empty / undefined)
      - A public IP not in the declared intranet CIDRs

    Allows:
      - "127.0.0.1", "::1", "localhost" unconditionally
      - Private IPs within allowed_intranet CIDRs from network_policy.yaml
    """
    if host in ("0.0.0.0", "::", ""):
        raise BindingSecurityError(
            f"Binding to '{host}' is strictly prohibited. "
            "The server must bind to 127.0.0.1, ::1, or a declared intranet CIDR. "
            "Binding to all interfaces exposes the workbench to unauthorized subnets."
        )

    # Loopback shortcuts
    if host.lower() == "localhost" or host in ("127.0.0.1", "::1"):
        return

    # Try to parse as an IP address
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # Not a valid IP — might be a hostname like "localhost" (already handled),
        # or a resolvable hostname. Attempt resolution.
        try:
            resolved = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            if not resolved:
                raise BindingSecurityError(
                    f"Cannot resolve hostname '{host}' to any IP address."
                )
            # Check the first resolved address
            ip_str = resolved[0][4][0]
            ip = ipaddress.ip_address(ip_str)
        except socket.gaierror:
            raise BindingSecurityError(
                f"Cannot resolve hostname '{host}'. "
                "Non-resolvable, non-loopback hostnames are rejected."
            )

    # Check if it's loopback
    if ip.is_loopback:
        return

    # For non-loopback IPs, validate against intranet CIDRs
    if policy_engine is None:
        from sovereign.config.settings import DEFAULT_POLICY_PATH
        policy_engine = NetworkPolicyEngine(str(DEFAULT_POLICY_PATH))

    for cidr in policy_engine.allowed_intranet:
        if ip in cidr:
            return

    raise BindingSecurityError(
        f"Binding to '{host}' is not permitted. "
        f"The IP {ip} does not fall within any declared intranet CIDR. "
        "Only loopback (127.0.0.1, ::1) and configured intranet ranges are allowed."
    )


class ServerConfig(BaseModel):
    """Configuration for the Sovereign FastAPI server."""
    host: str = Field(default="127.0.0.1", description="Server bind address")
    port: int = Field(default=8000, description="Server bind port")
    allowed_hosts: List[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "::1"],
        description="Allowed Host header values for DNS rebinding protection",
    )
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        description="Allowed CORS origins",
    )
    secret_key: str = Field(
        default="sovereign-dev-secret-key-change-in-production",
        description="Secret key for token signing",
    )
    static_dir: Optional[str] = Field(
        default=None,
        description="Path to static files directory",
    )

    def validate_binding(
        self, policy_engine: Optional[NetworkPolicyEngine] = None
    ) -> None:
        """Validate that the configured host is safe for binding."""
        validate_server_binding(self.host, policy_engine)


class HostHeaderMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that validates incoming Host headers against an allowlist.
    Defends against DNS rebinding attacks by rejecting requests with unrecognized
    Host values with HTTP 400 Bad Request.
    """

    def __init__(self, app, allowed_hosts: Optional[List[str]] = None):
        super().__init__(app)
        default_hosts = {"localhost", "127.0.0.1", "::1"}
        if allowed_hosts:
            self._allowed = default_hosts | {h.lower() for h in allowed_hosts}
        else:
            self._allowed = default_hosts

    async def dispatch(self, request: Request, call_next):
        host_header = request.headers.get("host", "")

        # Strip port number if present (e.g. "localhost:8000" -> "localhost")
        if ":" in host_header:
            # Handle IPv6 addresses in brackets like [::1]:8000
            if host_header.startswith("["):
                bracket_end = host_header.find("]")
                if bracket_end != -1:
                    host_value = host_header[1:bracket_end]
                else:
                    host_value = host_header
            else:
                host_value = host_header.rsplit(":", 1)[0]
        else:
            host_value = host_header

        host_value = host_value.lower().strip()

        if host_value not in self._allowed:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Host header"},
            )

        return await call_next(request)
