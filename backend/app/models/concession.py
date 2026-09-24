"""Concession model."""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedByMixin, TimestampMixin, UUIDPkMixin


class ConcessionStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Concession(Base, UUIDPkMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "concessions"
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    fee_head_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("fee_heads.id", ondelete="SET NULL"), nullable=True
    )
    installment_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("installments.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ConcessionStatus] = mapped_column(
        Enum(ConcessionStatus, name="concession_status"),
        nullable=False,
        default=ConcessionStatus.PENDING,
        server_default="PENDING",
    )
    approved_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_concessions_amount_positive"),
        Index("ix_concessions_student_id", "student_id"),
        Index("ix_concessions_status", "status"),
    )
