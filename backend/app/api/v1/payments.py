"""Payment routes (Package B)."""
from __future__ import annotations

import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, request_id_dep, require_role
from app.db.session import get_db
from app.models.payment import PaymentMethod, PaymentStatus
from app.models.user import Role, User
from app.schemas.common import Page
from app.schemas.payment import (
    AllocationRead,
    CounterPaymentRequest,
    InitiatePaymentRequest,
    InitiatePaymentResponse,
    PaymentDetail,
    PaymentRead,
    ReversalRead,
    ReversalRequest,
    VerifyPaymentResponse,
)
from app.services import payment_service, gateway_service

router = APIRouter(prefix="/payments", tags=["payments"])


def _to_read(p) -> PaymentRead:
    return PaymentRead.model_validate(p)


@router.post("/counter", response_model=PaymentDetail, status_code=201)
async def counter_payment(
    req: CounterPaymentRequest,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.FINANCE_STAFF.value, Role.FINANCE_MANAGER.value)),
) -> PaymentDetail:
    """Staff counter collection (cash/cheque) → SUCCESS direct + allocate."""
    try:
        p = payment_service.create_counter_payment(
            db,
            student_id=req.student_id,
            amount=req.amount,
            method=req.method,
            idempotency_key=req.idempotency_key,
            initiated_by=user.id,
            cheque_number=req.cheque_number,
        )
        return payment_service.get_payment_detail(db, p.id)
    except payment_service.IdempotencyConflict:
        raise HTTPException(409, detail={"error": {"code": "idempotency_conflict", "message": "idempotency key already used"}})
    except payment_service.InvalidStateTransition as e:
        raise HTTPException(422, detail={"error": {"code": "INVALID_STATE_TRANSITION", "message": str(e)}})


@router.post("/initiate", response_model=InitiatePaymentResponse, status_code=202)
async def initiate_payment(
    req: InitiatePaymentRequest,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.STUDENT.value, Role.FINANCE_STAFF.value)),
) -> InitiatePaymentResponse:
    """Student self-service via MockGateway → full async lifecycle."""
    if user.role == Role.STUDENT and user.student_id != req.student_id:
        raise HTTPException(403, detail={"error": {"code": "forbidden", "message": "students can only initiate payments for themselves"}})
    try:
        p, gref, redirect = payment_service.initiate_online_payment(
            db,
            student_id=req.student_id,
            amount=req.amount,
            idempotency_key=req.idempotency_key,
            initiated_by=user.id,
        )
    except payment_service.IdempotencyConflict:
        raise HTTPException(409, detail={"error": {"code": "idempotency_conflict", "message": "idempotency key already used"}})
    # Schedule the async gateway callback (fire-and-forget).
    asyncio.create_task(
        gateway_service.schedule_callback(p.id, gref, p.amount)
    )
    return InitiatePaymentResponse(
        payment_id=p.id, gateway_ref=gref, redirect_url=redirect, status=p.status
    )


@router.get("", response_model=Page[PaymentRead])
@router.get("/", response_model=Page[PaymentRead], include_in_schema=False)
async def list_payments(
    student_id: Optional[str] = Query(default=None),
    status_: Optional[PaymentStatus] = Query(default=None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.FINANCE_STAFF.value, Role.FINANCE_MANAGER.value, Role.ADMIN.value)),
) -> Page[PaymentRead]:
    items, total = payment_service.list_payments(
        db, student_id=student_id, status=status_, limit=limit, offset=offset
    )
    return Page[PaymentRead](items=[_to_read(p) for p in items], total=total, limit=limit, offset=offset)


@router.get("/{payment_id}", response_model=PaymentDetail)
async def get_payment(
    payment_id: str,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentDetail:
    try:
        detail = payment_service.get_payment_detail(db, payment_id)
    except payment_service.NotFound:
        raise HTTPException(404, detail={"error": {"code": "not_found", "message": "payment not found"}})
    # STUDENT may only view their own payments.
    if user.role == Role.STUDENT:
        p = detail.payment
        # Need the student's id; fetch via the payment's student_id and check
        # against the user's student_id.
        from app.models.student import Student
        s = db.get(Student, p.student_id)
        if not s or user.student_id != p.student_id:
            raise HTTPException(403, detail={"error": {"code": "forbidden", "message": "students can only view their own payments"}})
    return detail


@router.get("/{payment_id}/allocations", response_model=List[AllocationRead])
async def get_allocations(
    payment_id: str,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[AllocationRead]:
    from sqlalchemy import select
    from app.models.payment import PaymentAllocation
    rows = list(db.execute(
        select(PaymentAllocation).where(PaymentAllocation.payment_id == payment_id)
    ).scalars().all())
    return [AllocationRead.model_validate(r) for r in rows]


@router.post("/{payment_id}/verify", response_model=VerifyPaymentResponse)
async def verify_payment(
    payment_id: str,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.FINANCE_STAFF.value, Role.FINANCE_MANAGER.value)),
) -> VerifyPaymentResponse:
    """Resolve UNKNOWN payments by polling the gateway truth."""
    try:
        p = payment_service.verify_payment(db, payment_id, user.id)
    except payment_service.NotFound:
        raise HTTPException(404, detail={"error": {"code": "not_found", "message": "payment not found"}})
    return VerifyPaymentResponse(payment_id=p.id, status=p.status, message=f"resolved to {p.status.value}")


@router.post("/{payment_id}/reversal-request", response_model=ReversalRead, status_code=201)
async def reversal_request(
    payment_id: str,
    req: ReversalRequest,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.FINANCE_MANAGER.value, Role.ADMIN.value)),
) -> ReversalRead:
    try:
        rev = payment_service.request_reversal(db, payment_id, req.amount, req.reason, user.id)
    except payment_service.NotFound:
        raise HTTPException(404, detail={"error": {"code": "not_found", "message": "payment not found"}})
    except payment_service.InvalidStateTransition as e:
        raise HTTPException(409, detail={"error": {"code": "INVALID_STATE_TRANSITION", "message": str(e)}})
    except payment_service.AllocationExceedsOutstanding as e:
        raise HTTPException(422, detail={"error": {"code": "amount_exceeds_original", "message": str(e)}})
    return ReversalRead.model_validate(rev)


@router.post("/{payment_id}/reversal-complete", response_model=ReversalRead)
async def reversal_complete(
    payment_id: str,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(Role.FINANCE_MANAGER.value, Role.ADMIN.value)),
) -> ReversalRead:
    """Approve + complete a reversal (manager/admin)."""
    # Find the pending reversal for this payment.
    from sqlalchemy import select
    from app.models.payment import PaymentReversal, ReversalStatus
    rev = db.execute(
        select(PaymentReversal).where(
            PaymentReversal.original_payment_id == payment_id,
            PaymentReversal.status == ReversalStatus.REQUESTED,
        )
    ).scalar_one_or_none()
    if not rev:
        raise HTTPException(404, detail={"error": {"code": "not_found", "message": "no pending reversal for this payment"}})
    try:
        rev = payment_service.complete_reversal(db, rev.id, user.id)
    except payment_service.NotFound:
        raise HTTPException(404, detail={"error": {"code": "not_found", "message": "reversal not found"}})
    except payment_service.InvalidStateTransition as e:
        raise HTTPException(409, detail={"error": {"code": "INVALID_STATE_TRANSITION", "message": str(e)}})
    return ReversalRead.model_validate(rev)


@router.post("/webhook", include_in_schema=False)
async def payment_webhook(
    payload: dict,
    request_id: str = Depends(request_id_dep),
    db: Session = Depends(get_db),
):
    """Gateway async callback. Public (signed in prod; mock skips signature).

    SELECT ... FOR UPDATE on the payment row + idempotency on gateway_ref
    guarantee exactly-once processing even under duplicate callbacks.
    """
    from app.schemas.payment import WebhookPayload
    try:
        body = WebhookPayload.model_validate(payload)
    except Exception as e:
        raise HTTPException(422, detail={"error": {"code": "validation_error", "message": str(e)}})
    try:
        payment_service.apply_webhook_callback(
            db, body.gateway_ref, body.status, body.amount, actor_id=None
        )
    except payment_service.NotFound:
        # Return 200 so the gateway doesn't retry-penalize; log it.
        return {"status": "ignored", "reason": "gateway_ref not found"}
    except payment_service.InvalidStateTransition as e:
        return {"status": "ignored", "reason": str(e)}
    return {"status": "ok"}
