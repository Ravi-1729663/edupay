"""Idempotency key ledger — DB-enforced dedup for any entity."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin


class IdempotencyKey(Base, UUIDPkMixin):
    """One row per idempotency key. The `UNIQUE` constraint on `key` is the
    real enforcer; the service layer pre-checks for friendlier errors only."""

    __tablename__ = "idempotency_keys"
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_idempotency_entity", "entity_type"),
    )
