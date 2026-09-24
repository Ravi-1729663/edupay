"""Integrity checker schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel

from app.schemas.common import ORMBase


class Drift(ORMBase):
    student_id: str
    installment_id: str
    installment_number: int
    cached_status: str
    derived_status: str
    invoiced: str
    concessions: str
    allocated: str
    outstanding: str


class InvariantViolation(ORMBase):
    kind: str  # allocation_exceeds_payment | reversal_exceeds_original | impossible_payment_state | allocation_exceeds_installment
    entity_id: str
    detail: str


class IntegrityReport(ORMBase):
    ok: bool
    checked_at: datetime
    students_checked: int
    installments_checked: int
    payments_checked: int
    drifts: List[Drift]
    invariant_violations: List[InvariantViolation]
