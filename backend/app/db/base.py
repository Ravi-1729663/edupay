"""Declarative base + shared mixins."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Single declarative base for the whole project."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class CreatedByMixin:
    """FK to users.id; nullable for system rows (e.g. seed bootstrap)."""

    created_by: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )


class UUIDPkMixin:
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )
