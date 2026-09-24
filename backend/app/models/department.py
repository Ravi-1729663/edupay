"""Department + Program models."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import ForeignKey, Index, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class Department(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "departments"
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    programs: Mapped[List["Program"]] = relationship(
        back_populates="department", cascade="all, delete-orphan"
    )


class Program(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "programs"
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    duration_years: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    department: Mapped[Optional["Department"]] = relationship(back_populates="programs")

    __table_args__ = (
        Index("ix_programs_department_id", "department_id"),
    )
