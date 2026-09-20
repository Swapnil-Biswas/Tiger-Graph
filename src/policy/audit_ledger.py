"""
Cryptographic Tamper-Evident Audit Ledger (FRE 902(13)/(14) & FinCEN Compliant)
================================================================================
Maintains an immutable, append-only cryptographic hash chain of all agent actions,
verdicts, SAR filings, and supervisor overrides with HMAC-SHA256 signatures.
"""

import os
import json
import time
import hmac
import hashlib
import threading
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path


GENESIS_PREV_HASH = "0" * 64


@dataclass
class AuditLedgerEntry:
    index: int
    timestamp: str
    case_id: str
    actor: str
    action: str
    payload: Dict[str, Any]
    prev_hash: str
    entry_hash: str
    signature: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CryptographicAuditLedger:
    """Thread-safe, append-only tamper-evident cryptographic audit ledger."""

    def __init__(self, secret_key: Optional[bytes] = None):
        self.secret_key = secret_key or os.getenv("AUDIT_SECRET_KEY", "tigergraph-default-audit-key-2026").encode()
        self._lock = threading.RLock()
        self._entries: List[AuditLedgerEntry] = []

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def _canonical_bytes(self, index: int, timestamp: str, case_id: str, actor: str, action: str, payload: Dict[str, Any], prev_hash: str) -> bytes:
        """Create deterministic canonical byte representation for hashing and signing."""
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        canonical_str = f"{index}|{timestamp}|{case_id}|{actor}|{action}|{payload_json}|{prev_hash}"
        return canonical_str.encode("utf-8")

    def _compute_hash(self, canonical_bytes: bytes) -> str:
        """Compute SHA-256 hash of canonical bytes."""
        return hashlib.sha256(canonical_bytes).hexdigest()

    def _compute_signature(self, entry_hash: str) -> str:
        """Compute HMAC-SHA256 signature over entry hash."""
        return hmac.new(self.secret_key, entry_hash.encode("utf-8"), hashlib.sha256).hexdigest()

    def append(self, case_id: str, actor: str, action: str, payload: Optional[Dict[str, Any]] = None) -> AuditLedgerEntry:
        """Append a new action to the cryptographic audit chain."""
        with self._lock:
            payload_data = payload or {}
            index = len(self._entries)
            prev_hash = self._entries[-1].entry_hash if index > 0 else GENESIS_PREV_HASH
            ts = datetime.now(timezone.utc).isoformat()

            canonical_bytes = self._canonical_bytes(index, ts, case_id, actor, action, payload_data, prev_hash)
            entry_hash = self._compute_hash(canonical_bytes)
            sig = self._compute_signature(entry_hash)

            entry = AuditLedgerEntry(
                index=index,
                timestamp=ts,
                case_id=case_id,
                actor=actor,
                action=action,
                payload=payload_data,
                prev_hash=prev_hash,
                entry_hash=entry_hash,
                signature=sig,
            )
            self._entries.append(entry)
            return entry

    def verify_chain(self) -> Tuple[bool, str]:
        """Verify the cryptographic integrity of the entire audit chain."""
        with self._lock:
            if not self._entries:
                return True, "Audit chain is empty (valid)"

            expected_prev_hash = GENESIS_PREV_HASH

            for idx, entry in enumerate(self._entries):
                # 1. Verify index sequence
                if entry.index != idx:
                    return False, f"Broken sequence at index {idx}: entry has index {entry.index}"

                # 2. Verify previous hash chaining
                if entry.prev_hash != expected_prev_hash:
                    return False, f"Broken hash chain at index {idx}: expected prev_hash {expected_prev_hash}, got {entry.prev_hash}"

                # 3. Recompute canonical hash
                canonical_bytes = self._canonical_bytes(
                    entry.index, entry.timestamp, entry.case_id, entry.actor, entry.action, entry.payload, entry.prev_hash
                )
                computed_hash = self._compute_hash(canonical_bytes)
                if computed_hash != entry.entry_hash:
                    return False, f"Tampered content at index {idx}: hash mismatch ({computed_hash} != {entry.entry_hash})"

                # 4. Verify HMAC-SHA256 signature
                computed_sig = self._compute_signature(entry.entry_hash)
                if not hmac.compare_digest(computed_sig, entry.signature):
                    return False, f"Invalid signature at index {idx}: signature mismatch"

                expected_prev_hash = entry.entry_hash

            return True, f"All {len(self._entries)} audit entries cryptographically verified (100% intact)"

    def get_entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve latest entries."""
        with self._lock:
            return [e.to_dict() for e in self._entries[-limit:]]

    def export_json(self, file_path: Path) -> None:
        """Export ledger to JSON file."""
        with self._lock:
            data = [e.to_dict() for e in self._entries]
            file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def import_json(self, file_path: Path) -> Tuple[bool, str]:
        """Import ledger from JSON file and verify."""
        with self._lock:
            try:
                raw_data = json.loads(file_path.read_text(encoding="utf-8"))
            except Exception as e:
                return False, f"Failed to parse JSON: {e}"

            imported_entries = []
            for item in raw_data:
                entry = AuditLedgerEntry(
                    index=item["index"],
                    timestamp=item["timestamp"],
                    case_id=item["case_id"],
                    actor=item["actor"],
                    action=item["action"],
                    payload=item["payload"],
                    prev_hash=item["prev_hash"],
                    entry_hash=item["entry_hash"],
                    signature=item["signature"],
                )
                imported_entries.append(entry)

            self._entries = imported_entries
            return self.verify_chain()


_GLOBAL_LEDGER = CryptographicAuditLedger()


def get_audit_ledger() -> CryptographicAuditLedger:
    """Get global singleton audit ledger."""
    return _GLOBAL_LEDGER
