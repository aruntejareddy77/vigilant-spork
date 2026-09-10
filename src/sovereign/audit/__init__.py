"""
src/sovereign/audit/__init__.py
Cryptographic Audit Subsystem exports.
"""
from sovereign.audit.canonical import GENESIS_PREVIOUS_HASH, canonicalize_and_hash, verify_record
from sovereign.audit.ledger import AuditLedger
from sovereign.audit.mirror import AuditMirror
from sovereign.audit.models import AuditEvent
from sovereign.audit.verifier import (
    AuditTamperException,
    VerificationResult,
    verify_ledger,
    verify_ledger_tip,
)

__all__ = [
    "AuditEvent",
    "AuditLedger",
    "AuditMirror",
    "AuditTamperException",
    "VerificationResult",
    "canonicalize_and_hash",
    "verify_record",
    "verify_ledger",
    "verify_ledger_tip",
    "GENESIS_PREVIOUS_HASH",
]
