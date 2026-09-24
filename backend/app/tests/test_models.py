"""Model constraint tests — exercise DB-level invariants directly."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models.department import Department, Program
from app.models.fee import (
    FeeHead,
    FeeStructure,
    FeeStructureLine,
    Installment,
    StudentFeeAssignment,
)
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.student import Student, StudentStatus
from app.models.user import Role, User
from app.tests.conftest import login  # noqa: F401  (ensures seed ran)


def test_payment_amount_must_be_positive(db) -> None:
    # Find a seeded student to attach the payment to.
    from sqlalchemy import select
    s = db.execute(select(Student).limit(1)).scalar_one()
    u = db.execute(select(User).limit(1)).scalar_one()
    with pytest.raises(IntegrityError):
        db.add(
            Payment(
                student_id=s.id,
                amount=Decimal("0.00"),
                method=PaymentMethod.CASH,
                status=PaymentStatus.CREATED,
                initiated_by=u.id,
            )
        )
        db.flush()


def test_online_payment_requires_gateway_ref(db) -> None:
    from sqlalchemy import select
    s = db.execute(select(Student).limit(1)).scalar_one()
    u = db.execute(select(User).limit(1)).scalar_one()
    with pytest.raises(IntegrityError):
        db.add(
            Payment(
                student_id=s.id,
                amount=Decimal("100.00"),
                method=PaymentMethod.ONLINE,
                gateway_ref=None,
                status=PaymentStatus.PENDING,
                initiated_by=u.id,
            )
        )
        db.flush()


def test_gateway_ref_unique_idempotency(db) -> None:
    """Same gateway_ref twice must violate the unique constraint."""
    from sqlalchemy import select
    s = db.execute(select(Student).limit(1)).scalar_one()
    u = db.execute(select(User).limit(1)).scalar_one()
    p1 = Payment(
        student_id=s.id,
        amount=Decimal("100.00"),
        method=PaymentMethod.ONLINE,
        gateway_ref="GWAY-DUP-1",
        status=PaymentStatus.SUCCESS,
        initiated_by=u.id,
    )
    db.add(p1)
    db.flush()
    p2 = Payment(
        student_id=s.id,
        amount=Decimal("50.00"),
        method=PaymentMethod.ONLINE,
        gateway_ref="GWAY-DUP-1",  # duplicate!
        status=PaymentStatus.SUCCESS,
        initiated_by=u.id,
    )
    db.add(p2)
    with pytest.raises(IntegrityError):
        db.flush()


def test_idempotency_key_unique(db) -> None:
    from sqlalchemy import select
    s = db.execute(select(Student).limit(1)).scalar_one()
    u = db.execute(select(User).limit(1)).scalar_one()
    p1 = Payment(
        student_id=s.id,
        amount=Decimal("100.00"),
        method=PaymentMethod.CASH,
        idempotency_key="IDEM-1",
        status=PaymentStatus.SUCCESS,
        initiated_by=u.id,
    )
    db.add(p1)
    db.flush()
    p2 = Payment(
        student_id=s.id,
        amount=Decimal("100.00"),
        method=PaymentMethod.CASH,
        idempotency_key="IDEM-1",  # duplicate
        status=PaymentStatus.SUCCESS,
        initiated_by=u.id,
    )
    db.add(p2)
    with pytest.raises(IntegrityError):
        db.flush()


def test_installment_amount_positive(db) -> None:
    from sqlalchemy import select
    assignment = db.execute(select(StudentFeeAssignment).limit(1)).scalar_one()
    with pytest.raises(IntegrityError):
        db.add(
            Installment(
                student_fee_assignment_id=assignment.id,
                installment_number=99,
                due_date=__import__("datetime").date.today(),
                amount=Decimal("0.00"),
            )
        )
        db.flush()


def test_installment_unique_assignment_number(db) -> None:
    from sqlalchemy import select
    assignment = db.execute(select(StudentFeeAssignment).limit(1)).scalar_one()
    existing = db.execute(
        select(Installment).where(Installment.student_fee_assignment_id == assignment.id)
    ).scalars().first()
    from datetime import date, timedelta
    with pytest.raises(IntegrityError):
        db.add(
            Installment(
                student_fee_assignment_id=assignment.id,
                installment_number=existing.installment_number,
                due_date=date.today() + timedelta(days=1),
                amount=Decimal("10.00"),
            )
        )
        db.flush()


def test_fee_structure_line_amount_positive(db) -> None:
    fs = db.execute(select(FeeStructure).limit(1)).scalar_one()
    fh = db.execute(select(FeeHead).limit(1)).scalar_one()
    with pytest.raises(IntegrityError):
        db.add(
            FeeStructureLine(
                fee_structure_id=fs.id,
                fee_head_id=fh.id,
                amount=Decimal("-1.00"),
            )
        )
        db.flush()


def test_user_email_unique(db) -> None:
    existing = db.execute(select(User).where(User.email == "admin@edupay.college")).scalar_one()
    with pytest.raises(IntegrityError):
        db.add(
            User(
                email="admin@edupay.college",
                password_hash="x",
                full_name="Dup",
                role=Role.ADMIN,
            )
        )
        db.flush()


def test_department_code_unique(db) -> None:
    existing = db.execute(select(Department).where(Department.code == "CS")).scalar_one()
    with pytest.raises(IntegrityError):
        db.add(Department(code="CS", name="Dup Dept"))
        db.flush()


def test_program_code_unique(db) -> None:
    existing = db.execute(select(Program).where(Program.code == "BTECH-CS")).scalar_one()
    with pytest.raises(IntegrityError):
        db.add(Program(code="BTECH-CS", name="Dup", department_id=existing.department_id, duration_years=4))
        db.flush()


def test_student_roll_unique(db) -> None:
    existing = db.execute(select(Student).where(Student.roll_number == "STU20240001")).scalar_one()
    p = existing.program_id
    with pytest.raises(IntegrityError):
        db.add(
            Student(
                roll_number="STU20240001",
                full_name="Dup",
                email="dup@x.test",
                program_id=p,
                batch_year=2024,
                status=StudentStatus.ACTIVE,
            )
        )
        db.flush()
