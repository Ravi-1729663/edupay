"""Integrity checker — the differentiator.

Recomputes every student's outstanding from base facts
`(invoices − concessions − allocations)` and reports any drift vs the cached
`installments.status`. Also verifies the cross-row invariants documented in
`docs/DATA_MODEL.md`:

  1. Σ allocations ≤ payment.amount  for each payment
  2. Σ reversals   ≤ payment.amount  for each payment
  3. Σ allocations ≤ installment.amount − Σ approved concessions on it
  4. SUCCESS payments are not in an impossible state (no allocations AND no
     `metadata.unallocated=true`); REVERSED payments have a COMPLETED reversal

Pure-SQLAlchemy; never mutates. `app/tests/test_integrity.py` asserts zero
drift on freshly seeded data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.concession import Concession, ConcessionStatus
from app.models.fee import Installment, InstallmentStatus, StudentFeeAssignment
from app.models.payment import (
    Payment,
    PaymentAllocation,
    PaymentReversal,
    PaymentStatus,
    ReversalStatus,
)
from app.schemas.integrity import Drift, IntegrityReport, InvariantViolation

log = get_logger(__name__)

_ZERO = Decimal("0.00")


def check(db: Session) -> IntegrityReport:
    now = datetime.now(timezone.utc)

    # ── 1. Per-installment derived outstanding vs cached status ──
    # Only allocations from non-reversed payments (SUCCESS, REVERSAL_REQUESTED)
    # count toward outstanding. A REVERSED payment's allocations are voided
    # (the reversal restores the outstanding). This is the source of truth
    # the integrity checker recomputes from base facts.
    alloc_subq = (
        select(
            PaymentAllocation.installment_id,
            func.coalesce(func.sum(PaymentAllocation.amount), _ZERO).label("allocated"),
        )
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(
            Payment.status.in_([PaymentStatus.SUCCESS, PaymentStatus.REVERSAL_REQUESTED])
        )
        .group_by(PaymentAllocation.installment_id)
        .subquery()
    )
    conc_direct_subq = (
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
            Installment.id.label("installment_id"),
            Installment.student_fee_assignment_id,
            StudentFeeAssignment.student_id.label("student_id"),
            Installment.installment_number,
            Installment.amount.label("invoiced"),
            Installment.status.label("cached_status"),
            Installment.due_date,
            func.coalesce(alloc_subq.c.allocated, _ZERO).label("allocated"),
            func.coalesce(conc_direct_subq.c.concessions, _ZERO).label("concessions"),
        )
        .select_from(Installment)
        .join(
            StudentFeeAssignment,
            StudentFeeAssignment.id == Installment.student_fee_assignment_id,
        )
        .outerjoin(alloc_subq, alloc_subq.c.installment_id == Installment.id)
        .outerjoin(
            conc_direct_subq,
            conc_direct_subq.c.installment_id == Installment.id,
        )
    )
    rows = db.execute(stmt).all()

    drifts: List[Drift] = []
    students_checked = set()
    today = now.date()

    for r in rows:
        students_checked.add(str(r.student_id))
        invoiced = Decimal(r.invoiced or _ZERO)
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

        if cached_str != derived:
            drifts.append(
                Drift(
                    student_id=str(r.student_id),
                    installment_id=str(r.installment_id),
                    installment_number=int(r.installment_number),
                    cached_status=cached_str,
                    derived_status=derived,
                    invoiced=f"{invoiced:.2f}",
                    concessions=f"{concessions:.2f}",
                    allocated=f"{allocated:.2f}",
                    outstanding=f"{outstanding:.2f}",
                )
            )

    # ── 2. Cross-row invariants ──
    violations: List[InvariantViolation] = []

    palloc = (
        select(
            PaymentAllocation.payment_id,
            func.sum(PaymentAllocation.amount).label("allocated"),
        )
        .group_by(PaymentAllocation.payment_id)
        .subquery()
    )
    prev_subq = (
        select(
            PaymentReversal.original_payment_id,
            func.sum(PaymentReversal.amount).label("reversed"),
        )
        .group_by(PaymentReversal.original_payment_id)
        .subquery()
    )

    # 2a. allocations ≤ payment.amount
    over_alloc = db.execute(
        select(Payment.id, Payment.amount, func.coalesce(palloc.c.allocated, _ZERO))
        .select_from(Payment)
        .outerjoin(palloc, palloc.c.payment_id == Payment.id)
        .where(palloc.c.allocated > Payment.amount)
    ).all()
    for row in over_alloc:
        violations.append(
            InvariantViolation(
                kind="allocation_exceeds_payment",
                entity_id=str(row.id),
                detail=f"allocated {row[2]:.2f} > payment {row.amount:.2f}",
            )
        )

    # 2b. reversals ≤ payment.amount
    over_rev = db.execute(
        select(Payment.id, Payment.amount, func.coalesce(prev_subq.c.reversed, _ZERO))
        .select_from(Payment)
        .outerjoin(prev_subq, prev_subq.c.original_payment_id == Payment.id)
        .where(prev_subq.c.reversed > Payment.amount)
    ).all()
    for row in over_rev:
        violations.append(
            InvariantViolation(
                kind="reversal_exceeds_original",
                entity_id=str(row.id),
                detail=f"reversed {row[2]:.2f} > payment {row.amount:.2f}",
            )
        )

    # 2c. allocations ≤ installment.amount − concessions
    over_inst = db.execute(
        select(
            Installment.id,
            Installment.amount,
            func.coalesce(alloc_subq.c.allocated, _ZERO),
            func.coalesce(conc_direct_subq.c.concessions, _ZERO),
        )
        .select_from(Installment)
        .outerjoin(alloc_subq, alloc_subq.c.installment_id == Installment.id)
        .outerjoin(
            conc_direct_subq,
            conc_direct_subq.c.installment_id == Installment.id,
        )
        .where(
            func.coalesce(alloc_subq.c.allocated, _ZERO)
            > Installment.amount
            - func.coalesce(conc_direct_subq.c.concessions, _ZERO)
        )
    ).all()
    for row in over_inst:
        violations.append(
            InvariantViolation(
                kind="allocation_exceeds_installment",
                entity_id=str(row.id),
                detail=f"allocated {row[2]:.2f} > amount {row.amount:.2f} − concessions {row[3]:.2f}",
            )
        )

    # 2d. SUCCESS with no allocations and no unallocated flag
    succ_no_alloc = db.execute(
        select(Payment.id)
        .select_from(Payment)
        .outerjoin(palloc, palloc.c.payment_id == Payment.id)
        .where(
            Payment.status == PaymentStatus.SUCCESS,
            palloc.c.allocated.is_(None),
        )
    ).all()
    for (pid,) in succ_no_alloc:
        p = db.get(Payment, pid)
        md = (p.metadata_ or {}) if p else {}
        if not md.get("unallocated"):
            violations.append(
                InvariantViolation(
                    kind="impossible_payment_state",
                    entity_id=str(pid),
                    detail="SUCCESS payment with no allocations and no unallocated flag",
                )
            )

    # 2e. REVERSED payment with no COMPLETED reversal
    rev_no_complete = db.execute(
        select(Payment.id)
        .select_from(Payment)
        .outerjoin(
            PaymentReversal,
            (PaymentReversal.original_payment_id == Payment.id)
            & (PaymentReversal.status == ReversalStatus.COMPLETED),
        )
        .where(Payment.status == PaymentStatus.REVERSED)
        .group_by(Payment.id)
        .having(func.count(PaymentReversal.id) == 0)
    ).all()
    for (pid,) in rev_no_complete:
        violations.append(
            InvariantViolation(
                kind="impossible_payment_state",
                entity_id=str(pid),
                detail="REVERSED payment with no COMPLETED reversal",
            )
        )

    payments_checked = db.execute(
        select(func.count()).select_from(Payment)
    ).scalar_one()

    return IntegrityReport(
        ok=(not drifts and not violations),
        checked_at=now,
        students_checked=len(students_checked),
        installments_checked=len(rows),
        payments_checked=int(payments_checked or 0),
        drifts=drifts,
        invariant_violations=violations,
    )
