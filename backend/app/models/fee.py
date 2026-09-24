"""Fee catalog: FeeHead, FeeStructure, FeeStructureLine, StudentFeeAssignment, Installment."""
from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedByMixin, TimestampMixin, UUIDPkMixin


class FeeHead(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "fee_heads"
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=100)
    is_refundable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    structure_lines: Mapped[List["FeeStructureLine"]] = relationship(
        back_populates="fee_head"
    )

    __table_args__ = (
        Index("ix_fee_heads_priority", "priority"),
    )


class FeeStructure(Base, UUIDPkMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "fee_structures"
    program_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False
    )
    academic_year: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    lines: Mapped[List["FeeStructureLine"]] = relationship(
        back_populates="fee_structure", cascade="all, delete-orphan"
    )
    assignments: Mapped[List["StudentFeeAssignment"]] = relationship(
        back_populates="fee_structure"
    )

    __table_args__ = (
        UniqueConstraint("program_id", "academic_year", name="uq_fee_structures_program_year"),
        Index("ix_fee_structures_is_active", "is_active"),
    )


class FeeStructureLine(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "fee_structure_lines"
    fee_structure_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fee_structures.id", ondelete="CASCADE"), nullable=False
    )
    fee_head_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fee_heads.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    fee_structure: Mapped[Optional["FeeStructure"]] = relationship(back_populates="lines")
    fee_head: Mapped[Optional["FeeHead"]] = relationship(back_populates="structure_lines")

    __table_args__ = (
        UniqueConstraint(
            "fee_structure_id", "fee_head_id", name="uq_fsl_structure_head"
        ),
        CheckConstraint("amount > 0", name="ck_fsl_amount_positive"),
    )


class StudentFeeAssignment(Base, UUIDPkMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "student_fee_assignments"
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    fee_structure_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("fee_structures.id", ondelete="RESTRICT"), nullable=False
    )
    academic_year: Mapped[str] = mapped_column(String(16), nullable=False)
    total_invoiced: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    student: Mapped[Optional["Student"]] = relationship(back_populates="fee_assignments")  # type: ignore[name-defined]
    fee_structure: Mapped[Optional["FeeStructure"]] = relationship(back_populates="assignments")
    installments: Mapped[List["Installment"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "student_id", "academic_year", name="uq_sfa_student_year"
        ),
        CheckConstraint("total_invoiced >= 0", name="ck_sfa_total_nonneg"),
        Index("ix_sfa_student_id", "student_id"),
    )


class InstallmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"


class Installment(Base, UUIDPkMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "installments"
    student_fee_assignment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("student_fee_assignments.id", ondelete="CASCADE"),
        nullable=False,
    )
    installment_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fee_head_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("fee_heads.id", ondelete="SET NULL"), nullable=True
    )
    # Cached status — recomputed by integrity checker. Never the source of truth.
    status: Mapped[InstallmentStatus] = mapped_column(
        Enum(InstallmentStatus, name="installment_status"),
        nullable=False,
        default=InstallmentStatus.PENDING,
        server_default="PENDING",
    )

    assignment: Mapped[Optional["StudentFeeAssignment"]] = relationship(back_populates="installments")
    allocations: Mapped[List["PaymentAllocation"]] = relationship(  # type: ignore[name-defined]
        back_populates="installment"
    )

    __table_args__ = (
        UniqueConstraint(
            "student_fee_assignment_id",
            "installment_number",
            name="uq_installments_assignment_number",
        ),
        CheckConstraint("amount > 0", name="ck_installments_amount_positive"),
        Index("ix_installments_due_date", "due_date"),
        Index("ix_installments_assignment_id", "student_fee_assignment_id"),
        Index("ix_installments_status", "status"),
    )


# Late imports to resolve forward refs in this module.
from app.models.student import Student  # noqa: E402,F811
from app.models.payment import PaymentAllocation  # noqa: E402,F811
