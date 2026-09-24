"""Models package — imports register all tables on the Base.metadata."""
from app.models.user import User
from app.models.department import Department, Program
from app.models.student import Student
from app.models.fee import FeeHead, FeeStructure, FeeStructureLine, StudentFeeAssignment, Installment
from app.models.concession import Concession
from app.models.payment import Payment, PaymentAllocation, PaymentReversal
from app.models.reconciliation import ReconciliationBatch, ReconciliationLine
from app.models.idempotency import IdempotencyKey
from app.models.audit import AuditLog

__all__ = [
    "User",
    "Department",
    "Program",
    "Student",
    "FeeHead",
    "FeeStructure",
    "FeeStructureLine",
    "StudentFeeAssignment",
    "Installment",
    "Concession",
    "Payment",
    "PaymentAllocation",
    "PaymentReversal",
    "ReconciliationBatch",
    "ReconciliationLine",
    "IdempotencyKey",
    "AuditLog",
]
