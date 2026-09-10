"""
src/sovereign/audit/ledger.py
Process-safe append-only JSONL cryptographic ledger with advisory locking.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
import portalocker

from sovereign.audit.canonical import GENESIS_PREVIOUS_HASH, canonicalize_and_hash
from sovereign.audit.models import AuditEvent
from sovereign.audit.verifier import AuditTamperException, verify_ledger_tip


class AuditLedger:
    """
    Append-only cryptographic audit ledger. Writes records to an immutable JSONL file
    guarded by cross-platform advisory file locking (portalocker.Lock).
    """

    def __init__(self, ledger_path: str | Path, mirror: Optional[Any] = None):
        self.ledger_path = Path(ledger_path).resolve()
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.ledger_path.with_suffix(".lock")
        self.mirror = mirror

    def _get_tip_state(self) -> tuple[int, str]:
        """
        Reads the last valid record from the ledger file.
        Returns:
            (next_seq_num, previous_hash)
        """
        if not self.ledger_path.exists() or self.ledger_path.stat().st_size == 0:
            return 0, GENESIS_PREVIOUS_HASH

        last_line = ""
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    last_line = line_str

        if not last_line:
            return 0, GENESIS_PREVIOUS_HASH

        last_record = json.loads(last_line)
        next_seq = int(last_record["seq_num"]) + 1
        prev_hash = str(last_record["entry_hash"])
        return next_seq, prev_hash

    def append_event(
        self,
        session_id: str,
        event_type: str,
        actor_role: str,
        payload: Dict[str, Any],
        timestamp_iso: Optional[str] = None,
    ) -> AuditEvent:
        """
        Appends an event to the ledger under an exclusive advisory file lock.
        Calculates RFC 8785 canonical hash chained from the current ledger tip.
        """
        if timestamp_iso is None:
            timestamp_iso = datetime.now(timezone.utc).isoformat()

        # Acquire exclusive lock for reading the tip and appending
        with portalocker.Lock(str(self.lock_path), mode="a", timeout=10.0):
            # Guard: verify ledger tip integrity before appending
            is_valid, msg, _ = verify_ledger_tip(self.ledger_path)
            if not is_valid:
                raise AuditTamperException(f"Ledger tip integrity check failed: {msg}")

            next_seq, prev_hash = self._get_tip_state()

            record_dict, _ = canonicalize_and_hash(
                seq_num=next_seq,
                timestamp_iso=timestamp_iso,
                session_id=session_id,
                event_type=event_type,
                actor_role=actor_role,
                payload=payload,
                previous_hash=prev_hash,
            )

            # Strict validation using Pydantic model
            event = AuditEvent(**record_dict)

            # Append atomic single-line JSON
            json_line = json.dumps(record_dict, ensure_ascii=False)
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(json_line + "\n")
                f.flush()
                os.fsync(f.fileno())

            # Synchronously mirror if mirror is configured
            if self.mirror is not None:
                self.mirror.insert_event(event)

            return event
