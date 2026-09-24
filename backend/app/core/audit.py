"""Audit helper: writes one `audit_logs` row per state transition.

Every state transition (payment status change, concession decision, reversal,
reconciliation line resolution, etc.) MUST call `write_audit(...)`. The
function is tiny on purpose — it has no failure modes that would silently
swallow the transition.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging import get_logger

log = get_logger(__name__)


def write_audit(
    db: Session,
    *,
    actor_user_id: Optional[str],
    action: str,
    entity_type: str,
    entity_id: str,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Append one audit row. Commits within the caller's transaction."""
    payload = {
        "actor_user_id": actor_user_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "metadata_json": json.dumps(metadata or {}, default=str),
    }
    db.execute(
        text(
            """
            INSERT INTO audit_logs (actor_user_id, action, entity_type, entity_id, metadata)
            VALUES (:actor_user_id, :action, :entity_type, :entity_id, CAST(:metadata_json AS JSON))
            """
        ),
        payload,
    )
    # SQLite has no JSON type; the cast is harmless on Postgres. For SQLite we
    # rely on the column being declared as JSON (SQLAlchemy stores TEXT).
    log.info(
        "audit.write",
        extra={"action": action, "entity_type": entity_type, "entity_id": entity_id},
    )
