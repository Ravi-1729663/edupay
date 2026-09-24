"""Admin routes: integrity-check, audit-logs."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role, request_id_dep
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.user import Role, User
from app.schemas.common import Page
from app.schemas.integrity import IntegrityReport
from app.services.integrity_service import check as run_integrity_check

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/integrity-check", response_model=IntegrityReport)
async def integrity_check(
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.FINANCE_MANAGER.value, Role.ADMIN.value)),
) -> IntegrityReport:
    return run_integrity_check(db)


@router.get("/audit-logs")
async def list_audit_logs(
    entity_type: Optional[str] = Query(default=None),
    entity_id: Optional[str] = Query(default=None),
    actor_user_id: Optional[str] = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.FINANCE_MANAGER.value, Role.ADMIN.value)),
) -> dict:
    stmt = select(AuditLog)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    stmt = stmt.order_by(AuditLog.ts.desc(), AuditLog.id.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "actor_user_id": r.actor_user_id,
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "ts": r.ts.isoformat() if r.ts else None,
                "metadata": r.metadata_,
            }
            for r in rows
        ],
        "limit": limit,
        "offset": offset,
    }
