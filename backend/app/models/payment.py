"""Payment, PaymentAllocation, PaymentReversal models — the core financial records."""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedByMixin, TimestampMixin, UUIDPkMixin


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    CHEQUE = "CHEQUE"
    ONLINE = "ONLINE"


class PaymentStatus(str, enum.Enum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    REVERSAL_REQUESTED = "REVERSAL_REQUESTED"
    REVERSED = "REVERSED"


class Payment(Base, UUIDPkMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "payments"
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False
    )
    payer_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"), nullable=False
    )
    # UNIQUE — DB-enforced idempotency for gateway callbacks. NULL allowed
    # (cash/cheque), and on Postgres NULLs don't collide.
    gateway_ref: Mapped[Optional[str]] = mapped_column(
        String(128), unique=True, nullable=True
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"),
        nullable=False,
        default=PaymentStatus.CREATED,
        server_default="CREATED",
    )
    # UNIQUE — DB-enforced client idempotency.
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(128), unique=True, nullable=True
    )
    initiated_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    callback_received_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    allocations: Mapped[List["PaymentAllocation"]] = relationship(
        back_populates="payment", cascade="all, delete-orphan"
    )
    reversals: Mapped[List["PaymentReversal"]] = relationship(
        back_populates="original_payment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # An ONLINE payment MUST carry a gateway_ref.
        CheckConstraint(
            "method <> 'ONLINE' OR gateway_ref IS NOT NULL",
            name="ck_payments_online_requires_gateway_ref",
        ),
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        Index("ix_payments_student_id", "student_id"),
        Index("ix_payments_status", "status"),
        Index("ix_payments_created_at", "created_at"),
    )


class PaymentAllocation(Base, UUIDPkMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "payment_allocations"
    payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    installment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("installments.id", ondelete="RESTRICT"), nullable=False
    )
    fee_head_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fee_heads.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    payment: Mapped[Optional["Payment"]] = relationship(back_populates="allocations")
    installment: Mapped[Optional["Installment"]] = relationship(back_populates="allocations")  # type: ignore[name-defined]

    __table_args__ = (
        UniqueConstraint(
            "payment_id", "installment_id", "fee_head_id",
            name="uq_allocations_payment_installment_head",
        ),
        CheckConstraint("amount > 0", name="ck_allocations_amount_positive"),
        Index("ix_allocations_payment_id", "payment_id"),
        Index("ix_allocations_installment_id", "installment_id"),
    )


class ReversalStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    COMPLETED = "COMPLETED"


class PaymentReversal(Base, UUIDPkMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "payment_reversals"
    original_payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReversalStatus] = mapped_column(
        Enum(ReversalStatus, name="reversal_status"),
        nullable=False,
        default=ReversalStatus.REQUESTED,
        server_default="REQUESTED",
    )
    requested_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    original_payment: Mapped[Optional["Payment"]] = relationship(back_populates="reversals")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_reversals_amount_positive"),
        Index("ix_reversals_original_payment_id", "original_payment_id"),
    )


# Late import to resolve forward ref.
from app.models.fee import Installment  # noqa: E402,F811
