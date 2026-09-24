"""Payment state machine + allocation engine (Package B).

State machine (explicit transitions; anything else raises InvalidStateTransition):
    CREATED → PENDING                          (gateway ref issued)
    CREATED → SUCCESS                          (staff counter collection)
    PENDING → {SUCCESS | FAILED}              (gateway callback)
    PENDING → UNKNOWN                          (verify timeout)
    UNKNOWN → {SUCCESS | FAILED}               (verify resolution)
    SUCCESS → REVERSAL_REQUESTED               (reversal request)
    REVERSAL_REQUESTED → REVERSED              (manager approval)

Allocation engine:
    On SUCCESS, allocate the payment amount to the student's installments
    oldest-due-first (due_date ASC, installment_number ASC), then fee-head
    priority. Partial payments allowed. Allocation ≤ payment.amount AND
    allocation ≤ installment.outstanding (invoiced − concessions − prior
    allocations from non-reversed payments). Never over-allocates.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import write_audit
from app.core.logging import get_logger
from app.models.concession import Concession, ConcessionStatus
from app.models.fee import FeeHead, Installment, InstallmentStatus, StudentFeeAssignment
from app.models.payment import (
    Payment,
    PaymentAllocation,
    PaymentMethod,
    PaymentReversal,
    PaymentStatus,
    ReversalStatus,
)
from app.schemas.payment import AllocationRead, PaymentDetail, PaymentRead, ReversalRead

log = get_logger(__name__)

_ZERO = Decimal("0.00")


class InvalidStateTransition(Exception):
    """Raised when a payment state transition is not in the allowed table."""

    def __init__(self, current: str, target: str):
        self.current = current
        self.target = target
        super().__init__(
            f"invalid state transition: {current} → {target}"
        )


class IdempotencyConflict(Exception):
    """A payment with this idempotency key already exists."""


class AllocationExceedsOutstanding(Exception):
    pass


# Allowed transitions. Anything not listed → InvalidStateTransition.
_ALLOWED = {
    (PaymentStatus.CREATED, PaymentStatus.PENDING),
    (PaymentStatus.CREATED, PaymentStatus.SUCCESS),  # staff counter
    (PaymentStatus.PENDING, PaymentStatus.SUCCESS),
    (PaymentStatus.PENDING, PaymentStatus.FAILED),
    (PaymentStatus.PENDING, PaymentStatus.UNKNOWN),
    (PaymentStatus.UNKNOWN, PaymentStatus.SUCCESS),
    (PaymentStatus.UNKNOWN, PaymentStatus.FAILED),
    (PaymentStatus.SUCCESS, PaymentStatus.REVERSAL_REQUESTED),
    (PaymentStatus.REVERSAL_REQUESTED, PaymentStatus.REVERSED),
}


def transition(db: Session, payment: Payment, target: PaymentStatus, actor_id: str, *, metadata: Optional[dict] = None) -> Payment:
    """Validate + apply a state transition. Writes an audit row.

    Raises InvalidStateTransition if (current, target) not in _ALLOWED.
    Idempotent: a self-transition (current == target) for terminal states is
    treated as a no-op (e.g. a duplicate SUCCESS callback when already SUCCESS).
    """
    if payment.status == target and target in (PaymentStatus.SUCCESS, PaymentStatus.FAILED, PaymentStatus.REVERSED):
        # Idempotent re-callback: no-op, no audit row.
        return payment
    key = (payment.status, target)
    if key not in _ALLOWED:
        raise InvalidStateTransition(payment.status.value, target.value)
    prev = payment.status
    payment.status = target
    write_audit(
        db,
        actor_user_id=actor_id,
        action=f"payment.status_changed",
        entity_type="payment",
        entity_id=payment.id,
        metadata={"from": prev.value, "to": target.value, **(metadata or {})},
    )
    return payment


# ── Outstanding derivation (shared) ────────────────────────────────
def _installment_outstanding(db: Session, installment_id: str) -> Decimal:
    """invoiced − concessions − allocations_from_non_reversed_payments."""
    inst = db.get(Installment, installment_id)
    invoiced = inst.amount
    allocations = db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount), _ZERO))
        .join(Payment, Payment.id == PaymentAllocation.payment_id)
        .where(
            PaymentAllocation.installment_id == installment_id,
            Payment.status.in_([PaymentStatus.SUCCESS, PaymentStatus.REVERSAL_REQUESTED]),
        )
    ).scalar_one()
    concessions = db.execute(
        select(func.coalesce(func.sum(Concession.amount), _ZERO))
        .where(
            Concession.installment_id == installment_id,
            Concession.status == ConcessionStatus.APPROVED,
        )
    ).scalar_one()
    return Decimal(invoiced) - Decimal(allocations) - Decimal(concessions)


def _derived_installment_status(db: Session, inst: Installment, outstanding: Decimal) -> str:
    today = datetime.now(timezone.utc).date()
    if outstanding <= _ZERO:
        return InstallmentStatus.PAID.value
    if outstanding < inst.amount:
        return InstallmentStatus.PARTIALLY_PAID.value
    if inst.due_date < today:
        return InstallmentStatus.OVERDUE.value
    return InstallmentStatus.PENDING.value


def _refresh_installment_status(db: Session, inst: Installment) -> None:
    """Recompute + cache the installment status (the integrity checker verifies)."""
    outstanding = _installment_outstanding(db, inst.id)
    inst.status = InstallmentStatus(_derived_installment_status(db, inst, outstanding))


# ── Allocation engine ──────────────────────────────────────────────
def allocate(db: Session, payment: Payment, actor_id: str) -> List[PaymentAllocation]:
    """Oldest-due-first allocation. Returns the allocation rows created.

    Idempotent: if allocations already exist for this payment, returns them
    without creating duplicates (safe to call twice).
    """
    if payment.status != PaymentStatus.SUCCESS:
        raise InvalidStateTransition(payment.status.value, "ALLOCATE")
    existing = list(db.execute(
        select(PaymentAllocation).where(PaymentAllocation.payment_id == payment.id)
    ).scalars().all())
    if existing:
        return existing

    # Tuition head is the default for composite installments (priority 10).
    tuition = db.execute(
        select(FeeHead).where(FeeHead.code == "TUITION")
    ).scalar_one_or_none()

    # Installments oldest-due-first.
    installments = list(db.execute(
        select(Installment)
        .join(StudentFeeAssignment, StudentFeeAssignment.id == Installment.student_fee_assignment_id)
        .where(StudentFeeAssignment.student_id == payment.student_id)
        .order_by(Installment.due_date.asc(), Installment.installment_number.asc())
    ).scalars().all())

    remaining = Decimal(payment.amount)
    created: List[PaymentAllocation] = []
    touched_installments: List[Installment] = []
    for inst in installments:
        if remaining <= _ZERO:
            break
        outstanding = _installment_outstanding(db, inst.id)
        if outstanding <= _ZERO:
            continue
        alloc_amount = min(remaining, outstanding)
        if alloc_amount <= _ZERO:
            continue
        fee_head_id = inst.fee_head_id or (tuition.id if tuition else None)
        if not fee_head_id:
            # No head available — skip (shouldn't happen with seeded data).
            continue
        a = PaymentAllocation(
            payment_id=payment.id,
            installment_id=inst.id,
            fee_head_id=fee_head_id,
            amount=alloc_amount,
            created_by=actor_id,
        )
        db.add(a)
        created.append(a)
        remaining -= alloc_amount
        touched_installments.append(inst)

    # Flush so the just-added allocations are visible to the outstanding
    # recompute inside _refresh_installment_status (otherwise the cached
    # status would lag the new allocation and the integrity checker would
    # report drift).
    db.flush()
    for inst in touched_installments:
        _refresh_installment_status(db, inst)
    db.flush()
    write_audit(
        db,
        actor_user_id=actor_id,
        action="payment.allocated",
        entity_type="payment",
        entity_id=payment.id,
        metadata={
            "allocations": len(created),
            "allocated_total": str(payment.amount - remaining),
            "unallocated": str(remaining),
        },
    )
    return created


def _read_payment(db: Session, p: Payment) -> PaymentDetail:
    allocs = list(db.execute(
        select(PaymentAllocation).where(PaymentAllocation.payment_id == p.id)
    ).scalars().all())
    reversals = list(db.execute(
        select(PaymentReversal).where(PaymentReversal.original_payment_id == p.id)
    ).scalars().all())
    return PaymentDetail(
        payment=PaymentRead.model_validate(p),
        allocations=[AllocationRead.model_validate(a) for a in allocs],
        reversals=[ReversalRead.model_validate(r) for r in reversals],
    )


def get_payment_detail(db: Session, payment_id: str) -> PaymentDetail:
    p = db.get(Payment, payment_id)
    if not p:
        raise NotFound()
    return _read_payment(db, p)


class NotFound(Exception):
    pass


# ── Reversal ───────────────────────────────────────────────────────
def request_reversal(
    db: Session,
    payment_id: str,
    amount: Decimal,
    reason: str,
    requested_by: str,
) -> PaymentReversal:
    p = db.get(Payment, payment_id)
    if not p:
        raise NotFound()
    if p.status != PaymentStatus.SUCCESS:
        raise InvalidStateTransition(p.status.value, "REVERSAL_REQUESTED")
    if amount > p.amount:
        raise AllocationExceedsOutstanding("reversal exceeds original payment")
    rev = PaymentReversal(
        original_payment_id=p.id,
        amount=amount,
        reason=reason,
        status=ReversalStatus.REQUESTED,
        requested_by=requested_by,
        created_by=requested_by,
    )
    db.add(rev)
    db.flush()
    transition(db, p, PaymentStatus.REVERSAL_REQUESTED, requested_by, metadata={"reversal_id": rev.id})
    write_audit(
        db,
        actor_user_id=requested_by,
        action="reversal.requested",
        entity_type="payment_reversal",
        entity_id=rev.id,
        metadata={"original_payment_id": p.id, "amount": str(amount)},
    )
    db.commit()
    db.refresh(rev)
    return rev


def complete_reversal(db: Session, reversal_id: str, approver_id: str) -> PaymentReversal:
    rev = db.get(PaymentReversal, reversal_id)
    if not rev:
        raise NotFound()
    if rev.status != ReversalStatus.REQUESTED:
        raise InvalidStateTransition(f"reversal:{rev.status.value}", "COMPLETED")
    p = db.get(Payment, rev.original_payment_id)
    if not p:
        raise NotFound()
    # Reverse the payment → its allocations stop counting toward outstanding
    # (the outstanding derivation filters by status SUCCESS/REVERSAL_REQUESTED).
    transition(db, p, PaymentStatus.REVERSED, approver_id, metadata={"reversal_id": rev.id})
    rev.status = ReversalStatus.COMPLETED
    rev.completed_at = datetime.now(timezone.utc)
    # Flush so the REVERSED status + reversal row are visible to the
    # outstanding recompute below (autoflush is off on this session).
    db.flush()
    # Recompute affected installments' cached status.
    for a in p.allocations:
        _refresh_installment_status(db, db.get(Installment, a.installment_id))
    write_audit(
        db,
        actor_user_id=approver_id,
        action="reversal.completed",
        entity_type="payment_reversal",
        entity_id=rev.id,
        metadata={"original_payment_id": p.id, "amount": str(rev.amount)},
    )
    db.commit()
    db.refresh(rev)
    return rev


def list_payments(
    db: Session,
    *,
    student_id: Optional[str] = None,
    status: Optional[PaymentStatus] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Payment], int]:
    from sqlalchemy import func as _f

    stmt = select(Payment)
    count_stmt = select(_f.count()).select_from(Payment)
    if student_id:
        stmt = stmt.where(Payment.student_id == student_id)
        count_stmt = count_stmt.where(Payment.student_id == student_id)
    if status:
        stmt = stmt.where(Payment.status == status)
        count_stmt = count_stmt.where(Payment.status == status)
    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(Payment.created_at.desc()).limit(limit).offset(offset)
    items = list(db.execute(stmt).scalars().all())
    return items, int(total)


# ── High-level orchestration (called by routes) ────────────────────
def create_counter_payment(
    db: Session,
    *,
    student_id: str,
    amount: Decimal,
    method: PaymentMethod,
    idempotency_key: str,
    initiated_by: str,
    cheque_number: Optional[str] = None,
) -> Payment:
    """Staff counter collection (cash/cheque) → SUCCESS directly + allocate."""
    if method == PaymentMethod.ONLINE:
        raise InvalidStateTransition("ONLINE", "COUNTER")  # use initiate instead
    p = Payment(
        student_id=student_id,
        amount=amount,
        method=method,
        gateway_ref=None,
        status=PaymentStatus.CREATED,
        idempotency_key=idempotency_key,
        initiated_by=initiated_by,
        created_by=initiated_by,
        metadata_={"cheque_number": cheque_number} if cheque_number else None,
    )
    db.add(p)
    try:
        db.flush()
    except Exception as e:
        db.rollback()
        raise IdempotencyConflict(str(e))
    write_audit(
        db, actor_user_id=initiated_by, action="payment.counter_created",
        entity_type="payment", entity_id=p.id,
        metadata={"amount": str(amount), "method": method.value},
    )
    # CREATED → SUCCESS (staff counter skips PENDING).
    transition(db, p, PaymentStatus.SUCCESS, initiated_by, metadata={"mode": "counter"})
    p.callback_received_at = datetime.now(timezone.utc)
    db.flush()
    allocate(db, p, initiated_by)
    db.commit()
    db.refresh(p)
    return p


def initiate_online_payment(
    db: Session,
    *,
    student_id: str,
    amount: Decimal,
    idempotency_key: str,
    initiated_by: str,
    chaos: Optional[str] = None,
) -> tuple[Payment, str, str]:
    """Student self-service via MockGateway → full async lifecycle.

    Returns (payment, gateway_ref, redirect_url). The payment is in PENDING.

    The gateway_ref is generated up-front so the payment row satisfies the
    `ck_payments_online_requires_gateway_ref` CHECK constraint at INSERT time
    (an ONLINE payment must always carry a gateway_ref).
    """
    from app.services import gateway_service

    gateway_ref = gateway_service.new_gateway_ref()
    p = Payment(
        student_id=student_id,
        amount=amount,
        method=PaymentMethod.ONLINE,
        gateway_ref=gateway_ref,  # set at creation → CHECK passes
        status=PaymentStatus.CREATED,
        idempotency_key=idempotency_key,
        initiated_by=initiated_by,
        created_by=initiated_by,
    )
    db.add(p)
    try:
        db.flush()
    except Exception as e:
        db.rollback()
        raise IdempotencyConflict(str(e))
    transition(db, p, PaymentStatus.PENDING, initiated_by, metadata={"gateway_ref": gateway_ref})
    db.commit()
    db.refresh(p)
    redirect_url = f"/mock-gateway/redirect/{gateway_ref}"
    return p, gateway_ref, redirect_url


def apply_webhook_callback(
    db: Session,
    gateway_ref: str,
    status: PaymentStatus,
    amount: Decimal,
    actor_id: str = "gateway",
) -> Payment:
    """Process a gateway callback. SELECT FOR UPDATE on the payment row.

    Idempotent: a duplicate callback (same gateway_ref, already processed)
    returns the payment without creating new records.
    """
    # SELECT ... FOR UPDATE (no-op on SQLite; row-locks on Postgres).
    p = db.execute(
        select(Payment).where(Payment.gateway_ref == gateway_ref).with_for_update()
    ).scalar_one_or_none()
    if not p:
        raise NotFound()
    # Idempotent: already terminal.
    if p.status in (PaymentStatus.SUCCESS, PaymentStatus.FAILED, PaymentStatus.REVERSED):
        return p
    p.callback_received_at = datetime.now(timezone.utc)
    if status == PaymentStatus.SUCCESS:
        transition(db, p, PaymentStatus.SUCCESS, actor_id, metadata={"via": "webhook"})
        db.flush()
        allocate(db, p, actor_id)
    elif status == PaymentStatus.FAILED:
        transition(db, p, PaymentStatus.FAILED, actor_id, metadata={"via": "webhook"})
    else:
        raise InvalidStateTransition("PENDING", status.value)
    db.commit()
    db.refresh(p)
    return p


def verify_payment(db: Session, payment_id: str, actor_id: str) -> Payment:
    """Resolve PENDING → UNKNOWN (timeout) → SUCCESS/FAILED (via gateway truth)."""
    from app.services import gateway_service

    p = db.get(Payment, payment_id)
    if not p:
        raise NotFound()
    if p.status == PaymentStatus.PENDING:
        # Simulate "we polled the gateway, no callback yet" → UNKNOWN.
        transition(db, p, PaymentStatus.UNKNOWN, actor_id, metadata={"via": "verify_timeout"})
        db.commit()
        db.refresh(p)
        return p
    if p.status == PaymentStatus.UNKNOWN:
        true = gateway_service.get_true_outcome(p.gateway_ref) if p.gateway_ref else "UNKNOWN"
        if true == PaymentStatus.SUCCESS.value:
            transition(db, p, PaymentStatus.SUCCESS, actor_id, metadata={"via": "verify", "true_outcome": true})
            p.callback_received_at = datetime.now(timezone.utc)
            db.flush()
            allocate(db, p, actor_id)
        elif true == PaymentStatus.FAILED.value:
            transition(db, p, PaymentStatus.FAILED, actor_id, metadata={"via": "verify", "true_outcome": true})
        else:
            # Gateway doesn't know either — stay UNKNOWN.
            pass
        db.commit()
        db.refresh(p)
        return p
    # Already resolved.
    return p
