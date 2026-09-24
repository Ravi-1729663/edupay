"""Reconciliation routes (Package C)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_role, request_id_dep
from app.db.session import get_db
from app.models.reconciliation import ReconciliationClassification
from app.models.user import Role, User
from app.schemas.common import Page
from app.schemas.reconciliation import (
    BatchRead,
    BatchUploadResponse,
    LineRead,
    ResolveLineRequest,
)
from app.services import reconciliation_service

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


@router.post("/upload", response_model=BatchUploadResponse, status_code=201)
async def upload_settlement(
    file: UploadFile = File(...),
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.FINANCE_MANAGER.value, Role.ADMIN.value)),
) -> BatchUploadResponse:
    """Upload a settlement CSV (headers: external_reference, external_amount, [student_roll])."""
    content = (await file.read()).decode("utf-8", errors="replace")
    try:
        batch, lines = reconciliation_service.upload(
            db, csv_content=content, uploaded_by=user.id, source_file_name=file.filename or "settlement.csv"
        )
    except reconciliation_service.CSVParseError as e:
        raise HTTPException(422, detail={"error": {"code": "csv_parse_error", "message": str(e)}})
    return BatchUploadResponse(
        batch=BatchRead.model_validate(batch),
        lines=[LineRead.model_validate(ln) for ln in lines],
    )


@router.get("/batches", response_model=Page[BatchRead])
async def list_batches(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.FINANCE_MANAGER.value, Role.ADMIN.value)),
) -> Page[BatchRead]:
    items, total = reconciliation_service.list_batches(db, limit=limit, offset=offset)
    return Page[BatchRead](items=[BatchRead.model_validate(b) for b in items], total=total, limit=limit, offset=offset)


@router.get("/batches/{batch_id}", response_model=BatchRead)
async def get_batch(
    batch_id: str,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.FINANCE_MANAGER.value, Role.ADMIN.value)),
) -> BatchRead:
    try:
        return BatchRead.model_validate(reconciliation_service.get_batch(db, batch_id))
    except reconciliation_service.NotFound:
        raise HTTPException(404, detail={"error": {"code": "not_found", "message": "batch not found"}})


@router.get("/lines", response_model=Page[LineRead])
async def list_lines(
    batch_id: Optional[str] = Query(default=None),
    classification: Optional[ReconciliationClassification] = Query(default=None),
    resolved: Optional[bool] = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.FINANCE_MANAGER.value, Role.ADMIN.value)),
) -> Page[LineRead]:
    items, total = reconciliation_service.list_lines(
        db, batch_id=batch_id, classification=classification, resolved=resolved, limit=limit, offset=offset
    )
    return Page[LineRead](items=[LineRead.model_validate(ln) for ln in items], total=total, limit=limit, offset=offset)


@router.post("/lines/{line_id}/resolve", response_model=LineRead)
async def resolve_line(
    line_id: str,
    req: ResolveLineRequest,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.FINANCE_MANAGER.value, Role.ADMIN.value)),
) -> LineRead:
    """Manager-approved resolution. Does NOT mutate financial truth."""
    try:
        ln = reconciliation_service.resolve_line(
            db, line_id, resolved_classification=req.resolved_classification, notes=req.notes, resolved_by=user.id
        )
    except reconciliation_service.NotFound:
        raise HTTPException(404, detail={"error": {"code": "not_found", "message": "line not found"}})
    except reconciliation_service.AlreadyResolved:
        raise HTTPException(409, detail={"error": {"code": "already_resolved", "message": "line already resolved; resolutions are immutable"}})
    return LineRead.model_validate(ln)
