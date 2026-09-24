"""Payment + allocation + reversal schemas (Package B)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import Field

from app.models.payment import PaymentMethod, PaymentStatus, ReversalStatus
from app.schemas.common import ORMBase


class PaymentRead(ORMBase):
    id: str
    student_id: str
    payer_user_id: Optional[str] = None
    amount: Decimal = Field(decimal_places=2, max_digits=12)
    method: PaymentMethod
    gateway_ref: Optional[str] = None
    status: PaymentStatus
    idempotency_key: Optional[str] = None
    initiated_by: str
    callback_received_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AllocationRead(ORMBase):
    id: str
    payment_id: str
    installment_id: str
    fee_head_id: str
    amount: Decimal = Field(decimal_places=2, max_digits=12)
    created_at: datetime


class PaymentDetail(ORMBase):
    payment: PaymentRead
    allocations: List[AllocationRead]
    reversals: List["ReversalRead"]


class CounterPaymentRequest(ORMBase):
    """Staff counter collection (cash/cheque) → recorded as SUCCESS directly."""
    student_id: str
    amount: Decimal = Field(decimal_places=2, max_digits=12, gt=0)
    method: PaymentMethod  # CASH or CHEQUE
    cheque_number: Optional[str] = None
    idempotency_key: str = Field(min_length=1)
    # Optional explicit allocation; if omitted, the allocation engine runs
    # oldest-due-first automatically.
    allocate_to: Optional[List[dict]] = None


class InitiatePaymentRequest(ORMBase):
    """Student self-service via MockGateway → full async lifecycle."""
    student_id: str
    amount: Decimal = Field(decimal_places=2, max_digits=12, gt=0)
    method: PaymentMethod = PaymentMethod.ONLINE
    idempotency_key: str = Field(min_length=1)
    return_url: Optional[str] = None


class InitiatePaymentResponse(ORMBase):
    payment_id: str
    gateway_ref: str
    redirect_url: str
    status: PaymentStatus


class VerifyPaymentResponse(ORMBase):
    payment_id: str
    status: PaymentStatus
    message: str


class ReversalRequest(ORMBase):
    amount: Decimal = Field(decimal_places=2, max_digits=12, gt=0)
    reason: str = Field(min_length=1)


class ReversalRead(ORMBase):
    id: str
    original_payment_id: str
    amount: Decimal = Field(decimal_places=2, max_digits=12)
    reason: str
    status: ReversalStatus
    requested_by: str
    completed_at: Optional[datetime] = None
    created_at: datetime


# Forward ref
PaymentDetail.model_rebuild()


class GatewayPayRequest(ORMBase):
    """Internal: MockGateway receives this from /payments/initiate."""
    payment_id: str
    amount: Decimal = Field(decimal_places=2, max_digits=12)
    student_id: str
    idempotency_key: str
    chaos: Optional[str] = None  # overrides stored setting if provided


class GatewayPayResponse(ORMBase):
    gateway_ref: str
    redirect_url: str
    status: str = "PENDING"


class WebhookPayload(ORMBase):
    gateway_ref: str
    status: PaymentStatus  # SUCCESS or FAILED
    amount: Decimal = Field(decimal_places=2, max_digits=12)
    paid_at: Optional[datetime] = None


class ChaosSetting(ORMBase):
    mode: str  # SUCCESS | FAILED | TIMEOUT_NO_CALLBACK | DUPLICATE_CALLBACK | LATE_CALLBACK
    delay_seconds: int = 0
