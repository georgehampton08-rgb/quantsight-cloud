"""
Structured Audit Logger — Phase 7 Step 7.7
=============================================
Tamper-evident, queryable audit trail for all admin actions.
Required for SOC2 CC8.1 (Change Management).

Collection: audit_log (Firestore)
Document ID: {timestamp_ms}_{action_type}_{request_id_prefix}

Rules:
  - Never raises — audit failure must NOT block the primary operation
  - IP addresses are SHA256-hashed (privacy preservation)
  - TTL: 365 days (set via Firestore TTL policy on expires_at field)
  - actor is correlation_id or "system" for automated actions

Usage:
    from vanguard.audit.audit_logger import get_audit_logger
    audit = get_audit_logger()
    await audit.log(
        action="RESOLVE_INCIDENT",
        request_id="abc-123",
        affected_ids=["fp_001"],
        metadata={"approved": True},
        result="SUCCESS",
        ip_address="1.2.3.4",
    )
"""

import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)


class AuditLogger:
    """Write structured audit log entries to Firestore."""

    def __init__(self):
        self._collection = "audit_log"

    async def log(
        self,
        action: str,
        request_id: str,
        affected_ids: List[str],
        metadata: dict,
        result: str,
        ip_address: Optional[str] = None,
        actor: str = "system",
        service: str = "quantsight-vanguard",
    ) -> None:
        """
        Write an audit log entry to Firestore.

        Never raises — audit failure must not block the primary operation.
        """
        try:
            from vanguard.archivist.storage import get_incident_storage

            storage = get_incident_storage()

            now = datetime.now(timezone.utc)
            entry = {
                "actor": actor,
                "action": action,
                "timestamp_utc": now.isoformat(),
                "request_id": request_id,
                "affected_ids": affected_ids,
                "metadata": metadata,
                "result": result,
                "ip_address": self._hash_ip(ip_address),
                "service": service,
                "expires_at": (now + timedelta(days=365)).isoformat(),
            }

            doc_id = (
                f"{int(now.timestamp() * 1000)}"
                f"_{action}"
                f"_{request_id[:8] if request_id else 'unknown'}"
            )

            await storage.write_to_collection(
                self._collection,
                doc_id,
                entry,
            )

            logger.info(
                f"audit_log_written: action={action} "
                f"affected={len(affected_ids)} result={result}"
            )

        except Exception as e:
            # CRITICAL: Audit failure must NEVER block the primary operation
            logger.error(
                f"Audit log write failed: {e}. "
                f"Action={action} request_id={request_id} was NOT logged."
            )

    @staticmethod
    def _hash_ip(ip: Optional[str]) -> str:
        """Hash IP address for privacy preservation. Returns first 16 chars of SHA256."""
        if not ip:
            return "unknown"
        return hashlib.sha256(ip.encode()).hexdigest()[:16]


# ── Singleton ────────────────────────────────────────────────────────────
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create the global AuditLogger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
