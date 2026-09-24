"""Student + outstanding schemas."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import Field

from app.models.student import StudentStatus
from app.schemas.common import ORMBase


class StudentRead(ORMBase):
    id: str
    roll_number: str
    full_name: str
    email: str
    phone: Optional[str] = None
    program_id: str
    batch_year: int
    status: StudentStatus


class InstallmentOutstanding(ORMBase):
    installment_id: str
    installment_number: int
    due_date: date
    amount: Decimal = Field(decimal_places=2, max_digits=12)
    invoiced: Decimal = Field(decimal_places=2, max_digits=12)
    concessions: Decimal = Field(decimal_places=2, max_digits=12)
    allocated: Decimal = Field(decimal_places=2, max_digits=12)
    outstanding: Decimal = Field(decimal_places=2, max_digits=12)
    cached_status: str
    derived_status: str
    drift: bool


class StudentOutstanding(ORMBase):
    student_id: str
    total_invoiced: Decimal = Field(decimal_places=2, max_digits=12)
    total_concessions: Decimal = Field(decimal_places=2, max_digits=12)
    total_allocated: Decimal = Field(decimal_places=2, max_digits=12)
    total_outstanding: Decimal = Field(decimal_places=2, max_digits=12)
    by_installment: List[InstallmentOutstanding]


class InstallmentRead(ORMBase):
    id: str
    installment_number: int
    due_date: date
    amount: Decimal = Field(decimal_places=2, max_digits=12)
    fee_head_id: Optional[str] = None
    status: str
