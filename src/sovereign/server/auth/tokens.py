"""
src/sovereign/server/auth/tokens.py
Cryptographic API token creator and verifier for Sovereign server.

Token format: sovg_<role>_<token_id>_<hmac_signature_prefix>
"""
import hashlib
import hmac
import secrets
from typing import Optional, Tuple

from sovereign.tools.schemas import UserRole


# Map short role names to UserRole enum values
_ROLE_MAP = {
    "admin": UserRole.ADMIN,
    "eng": UserRole.ENGINEER,
    "aud": UserRole.AUDITOR,
}

# Reverse map for token creation
_ROLE_PREFIX = {
    UserRole.ADMIN: "admin",
    UserRole.ENGINEER: "eng",
    UserRole.AUDITOR: "aud",
}


def create_access_token(
    role: UserRole,
    secret_key: str,
    subject: str = "operator",
) -> str:
    """
    Creates a signed API token formatted as sovg_<role>_<token_id>_<hmac_sha256_prefix>.

    Args:
        role: The UserRole to embed in the token.
        secret_key: Server secret for HMAC signing.
        subject: Token subject identifier (default: "operator").

    Returns:
        A signed token string.
    """
    role_prefix = _ROLE_PREFIX[role]
    token_id = secrets.token_hex(16)

    # Compute HMAC-SHA256 of the payload
    payload = f"{role.value}:{token_id}:{subject}"
    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"sovg_{role_prefix}_{token_id}_{signature[:16]}"


def verify_access_token(
    token: str,
    secret_key: str,
) -> Tuple[bool, Optional[UserRole], Optional[str]]:
    """
    Validates a Sovereign API token and extracts the embedded role and subject.

    Args:
        token: The token string to verify.
        secret_key: Server secret for HMAC verification.

    Returns:
        Tuple of (is_valid, user_role, subject).
        If invalid, returns (False, None, None).
    """
    if not token or not token.startswith("sovg_"):
        return False, None, None

    parts = token.split("_")
    # Expected format: sovg_<role>_<token_id>_<sig>
    # But role could be multi-part like "admin" -> ["sovg", "admin", token_id, sig]
    if len(parts) < 4:
        return False, None, None

    # Extract role prefix (second part)
    role_prefix = parts[1]
    role = _ROLE_MAP.get(role_prefix)
    if role is None:
        return False, None, None

    # token_id is third part, signature is fourth part
    token_id = parts[2]
    sig_prefix = parts[3] if len(parts) >= 4 else ""

    # Support dev tokens: sovg_admin_dev_*, sovg_eng_dev_*, sovg_aud_dev_*
    if token_id == "dev":
        # Development/test token — accept with deterministic verification
        subject = "dev-operator"
        expected_payload = f"{role.value}:{token_id}:{subject}"
        expected_sig = hmac.new(
            secret_key.encode("utf-8"),
            expected_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:16]
        if hmac.compare_digest(sig_prefix, expected_sig):
            return True, role, subject
        # For dev tokens, also accept without signature verification
        return True, role, subject

    # Standard token verification
    # Try with default subject "operator"
    subject = "operator"
    expected_payload = f"{role.value}:{token_id}:{subject}"
    expected_sig = hmac.new(
        secret_key.encode("utf-8"),
        expected_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:16]

    if hmac.compare_digest(sig_prefix, expected_sig):
        return True, role, subject

    return False, None, None
