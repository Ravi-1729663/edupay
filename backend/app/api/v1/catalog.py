"""Catalog routes: departments, programs, fee-heads, fee-structures (read)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, request_id_dep
from app.db.session import get_db
from app.models.department import Department, Program
from app.models.fee import FeeHead, FeeStructure
from app.models.user import User

router = APIRouter(tags=["catalog"])


@router.get("/departments")
async def list_departments(
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[dict]:
    rows = db.execute(select(Department).order_by(Department.code)).scalars().all()
    return [{"id": r.id, "code": r.code, "name": r.name} for r in rows]


@router.get("/programs")
async def list_programs(
    department_id: Optional[str] = Query(default=None),
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[dict]:
    stmt = select(Program).order_by(Program.code)
    if department_id:
        stmt = stmt.where(Program.department_id == department_id)
    rows = db.execute(stmt).scalars().all()
    return [
        {"id": r.id, "code": r.code, "name": r.name, "department_id": r.department_id, "duration_years": r.duration_years}
        for r in rows
    ]


@router.get("/fee-heads")
async def list_fee_heads(
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[dict]:
    rows = db.execute(select(FeeHead).order_by(FeeHead.priority, FeeHead.code)).scalars().all()
    return [
        {"id": r.id, "code": r.code, "name": r.name, "description": r.description, "priority": r.priority, "is_refundable": r.is_refundable}
        for r in rows
    ]


@router.get("/fee-structures")
async def list_fee_structures(
    program_id: Optional[str] = Query(default=None),
    academic_year: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[dict]:
    stmt = select(FeeStructure).options(selectinload(FeeStructure.lines))
    if program_id:
        stmt = stmt.where(FeeStructure.program_id == program_id)
    if academic_year:
        stmt = stmt.where(FeeStructure.academic_year == academic_year)
    if is_active is not None:
        stmt = stmt.where(FeeStructure.is_active == is_active)
    stmt = stmt.order_by(FeeStructure.academic_year.desc())
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "id": r.id,
            "program_id": r.program_id,
            "academic_year": r.academic_year,
            "effective_from": r.effective_from.isoformat(),
            "effective_to": r.effective_to.isoformat(),
            "is_active": r.is_active,
            "lines": [
                {"id": ln.id, "fee_head_id": ln.fee_head_id, "amount": str(ln.amount)}
                for ln in r.lines
            ],
        }
        for r in rows
    ]
