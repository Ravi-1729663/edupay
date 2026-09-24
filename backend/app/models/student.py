"""Student model."""
from __future__ import annotations

import enum
from typing import List, Optional

from sqlalchemy import Enum, ForeignKey, Index, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedByMixin, TimestampMixin, UUIDPkMixin


class StudentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    GRADUATED = "GRADUATED"
    WITHDRAWN = "WITHDRAWN"


class Student(Base, UUIDPkMixin, TimestampMixin, CreatedByMixin):
    __tablename__ = "students"
    roll_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    program_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False
    )
    batch_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[StudentStatus] = mapped_column(
        Enum(StudentStatus, name="student_status"),
        nullable=False,
        default=StudentStatus.ACTIVE,
        server_default="ACTIVE",
    )

    fee_assignments: Mapped[List["StudentFeeAssignment"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_students_program_id", "program_id"),
        Index("ix_students_batch_year", "batch_year"),
        Index("ix_students_status", "status"),
    )
