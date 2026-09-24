"""Student routes: list, get, outstanding (derived), installments."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    require_active_student_self_or_staff,
    require_role,
    request_id_dep,
)
from app.db.session import get_db
from app.models.concession import Concession, ConcessionStatus
from app.models.fee import Installment, InstallmentStatus, StudentFeeAssignment
from app.models.payment import Payment, PaymentAllocation, PaymentStatus
from app.models.student import Student, StudentStatus
from app.models.user import Role, User
from app.schemas.common import Page
from app.schemas.student import (
    InstallmentOutstanding,
    InstallmentRead,
    StudentOutstanding,
    StudentRead,
)

router = APIRouter(prefix="/students", tags=["students"])

_ZERO = Decimal("0.00")


@router.get("", response_model=Page[StudentRead])
@router.get("/", response_model=Page[StudentRead], include_in_schema=False)
async def list_students(
    q: Optional[str] = Query(default=None),
    program_id: Optional[str] = Query(default=None),
    batch_year: Optional[int] = Query(default=None),
    status_: Optional[StudentStatus] = Query(default=None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.FINANCE_STAFF.value, Role.FINANCE_MANAGER.value, Role.ADMIN.value)),
) -> Page[StudentRead]:
    stmt = select(Student)
    count_stmt = select(func.count()).select_from(Student)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Student.roll_number.ilike(like), Student.full_name.ilike(like), Student.email.ilike(like)))
        count_stmt = count_stmt.where(or_(Student.roll_number.ilike(like), Student.full_name.ilike(like), Student.email.ilike(like)))
    if program_id:
        stmt = stmt.where(Student.program_id == program_id)
        count_stmt = count_stmt.where(Student.program_id == program_id)
    if batch_year:
        stmt = stmt.where(Student.batch_year == batch_year)
        count_stmt = count_stmt.where(Student.batch_year == batch_year)
    if status_:
        stmt = stmt.where(Student.status == status_)
        count_stmt = count_stmt.where(Student.status == status_)
    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(Student.roll_number).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
    return Page[StudentRead](
        items=[StudentRead.model_validate(r) for r in rows],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/{student_id}", response_model=StudentRead)
async def get_student(
    student_id: str,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_active_student_self_or_staff()),
) -> StudentRead:
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "student not found"}})
    return StudentRead.model_validate(s)


@router.get("/{student_id}/outstanding", response_model=StudentOutstanding)
async def get_outstanding(
    student_id: str,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_active_student_self_or_staff()),
) -> StudentOutstanding:
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "student not found"}})

    # Derived outstanding per installment: amount − concessions − allocations
    alloc_subq = (
        select(
            PaymentAllocation.installment_id,
            func.coalesce(func.sum(PaymentAllocation.amount), _ZERO).label("allocated"),
        )
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(Payment.status.in_([PaymentStatus.SUCCESS, PaymentStatus.REVERSAL_REQUESTED, PaymentStatus.REVERSED]))
        .group_by(PaymentAllocation.installment_id)
        .subquery()
    )
    conc_subq = (
        select(
            Concession.installment_id,
            func.coalesce(func.sum(Concession.amount), _ZERO).label("concessions"),
        )
        .where(Concession.status == ConcessionStatus.APPROVED)
        .group_by(Concession.installment_id)
        .subquery()
    )

    stmt = (
        select(
            Installment.id,
            Installment.installment_number,
            Installment.due_date,
            Installment.amount,
            func.coalesce(alloc_subq.c.allocated, _ZERO).label("allocated"),
            func.coalesce(conc_subq.c.concessions, _ZERO).label("concessions"),
            Installment.status.label("cached_status"),
        )
        .select_from(Installment)
        .join(StudentFeeAssignment, StudentFeeAssignment.id == Installment.student_fee_assignment_id)
        .where(StudentFeeAssignment.student_id == student_id)
        .outerjoin(alloc_subq, alloc_subq.c.installment_id == Installment.id)
        .outerjoin(conc_subq, conc_subq.c.installment_id == Installment.id)
        .order_by(Installment.due_date, Installment.installment_number)
    )
    rows = db.execute(stmt).all()
    today = date.today()
    by_inst: List[InstallmentOutstanding] = []
    tot_inv = tot_conc = tot_alloc = _ZERO
    for r in rows:
        invoiced = Decimal(r.amount or _ZERO)
        allocated = Decimal(r.allocated or _ZERO)
        concessions = Decimal(r.concessions or _ZERO)
        outstanding = invoiced - concessions - allocated
        if outstanding <= _ZERO:
            derived = InstallmentStatus.PAID.value
        elif outstanding < invoiced:
            derived = InstallmentStatus.PARTIALLY_PAID.value
        elif r.due_date < today:
            derived = InstallmentStatus.OVERDUE.value
        else:
            derived = InstallmentStatus.PENDING.value
        cached = r.cached_status
        cached_str = cached.value if hasattr(cached, "value") else str(cached)
        by_inst.append(
            InstallmentOutstanding(
                installment_id=r.id,
                installment_number=int(r.installment_number),
                due_date=r.due_date,
                amount=invoiced,
                invoiced=invoiced,
                concessions=concessions,
                allocated=allocated,
                outstanding=outstanding,
                cached_status=cached_str,
                derived_status=derived,
                drift=cached_str != derived,
            )
        )
        tot_inv += invoiced
        tot_conc += concessions
        tot_alloc += allocated

    return StudentOutstanding(
        student_id=student_id,
        total_invoiced=tot_inv,
        total_concessions=tot_conc,
        total_allocated=tot_alloc,
        total_outstanding=tot_inv - tot_conc - tot_alloc,
        by_installment=by_inst,
    )


@router.get("/{student_id}/installments", response_model=List[InstallmentRead])
async def list_installments(
    student_id: str,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_active_student_self_or_staff()),
) -> List[InstallmentRead]:
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "student not found"}})
    stmt = (
        select(Installment)
        .join(StudentFeeAssignment, StudentFeeAssignment.id == Installment.student_fee_assignment_id)
        .where(StudentFeeAssignment.student_id == student_id)
        .order_by(Installment.installment_number)
    )
    rows = db.execute(stmt).scalars().all()
    return [
        InstallmentRead(
            id=r.id,
            installment_number=r.installment_number,
            due_date=r.due_date,
            amount=r.amount,
            fee_head_id=r.fee_head_id,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
        )
        for r in rows
    ]
