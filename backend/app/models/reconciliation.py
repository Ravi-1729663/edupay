"""Reconciliation models."""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedByMixin, TimestampMixin, UUIDPkMixin


class ReconciliationClassification(str, enum.Enum):
    MATCHED = "MATCHED"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    MISSING_INTERNAL = "MISSING_INTERNAL"
    MISSING_EXTERNAL = "MISSING_EXTERNAL"
    DUPLICATE = "DUPLICATE"


class ReconciliationBatch(Base, UUIDPkMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "reconciliation_batches"
    uploaded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    source_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    total_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    amount_mismatch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    missing_internal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    missing_external_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class ReconciliationLine(Base, UUIDPkMixin, CreatedByMixin):
    """Note: does NOT inherit TimestampMixin — reconciliation lines are
    immutable write-once per batch; only `created_at` is meaningful.

    Package C adds the exception-review columns (resolved_*). Resolving a
    line never mutates financial truth (payments / allocations / installments)
    — it only records a FINANCE_MANAGER's decision about the settlement line."""

    __tablename__ = "reconciliation_lines"
    batch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reconciliation_batches.id", ondelete="CASCADE"), nullable=False
    )
    external_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    external_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    student_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="SET NULL"), nullable=True
    )
    payment_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )
    # Original engine classification (MATCHED/AMOUNT_MISMATCH/MISSING_INTERNAL/
    # MISSING_EXTERNAL/DUPLICATE). Never mutated after insert.
    classification: Mapped[ReconciliationClassification] = mapped_column(
        Enum(ReconciliationClassification, name="recon_class"),
        nullable=False,
    )
    # Engine's suggested match for human review (reference + date-window + amount).
    suggested_payment_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # ── Exception-review workflow (Package C) ──
    resolved_classification: Mapped[Optional[str]] = mapped_column(
        String(24), nullable=True
    )
    resolved_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("external_amount > 0", name="ck_recon_line_amount_positive"),
        Index("ix_recon_lines_batch_id", "batch_id"),
        Index("ix_recon_lines_external_reference", "external_reference"),
        Index("ix_recon_lines_resolved_classification", "resolved_classification"),
    )
