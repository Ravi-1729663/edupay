"""Reconciliation schemas (Package C)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import Field

from app.models.reconciliation import ReconciliationClassification
from app.schemas.common import ORMBase


class BatchRead(ORMBase):
    id: str
    uploaded_by: str
    source_file_name: str
    total_lines: int
    matched_count: int
    amount_mismatch_count: int
    missing_internal_count: int
    missing_external_count: int
    duplicate_count: int
    created_at: datetime


class LineRead(ORMBase):
    id: str
    batch_id: str
    external_reference: str
    external_amount: Decimal = Field(decimal_places=2, max_digits=12)
    student_id: Optional[str] = None
    payment_id: Optional[str] = None
    classification: ReconciliationClassification
    suggested_payment_id: Optional[str] = None
    notes: Optional[str] = None
    resolved_classification: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime


class BatchUploadResponse(ORMBase):
    batch: BatchRead
    lines: List[LineRead]


class ResolveLineRequest(ORMBase):
    resolved_classification: ReconciliationClassification
    notes: str = Field(min_length=1)
