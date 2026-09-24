"""Seed script v1 — re-runnable.

Creates the four role users, departments, programs, 6 fee heads, fee
structures, ~300 students (+ matching STUDENT-role users), fee assignments
with 3 installments each (due dates spread past/current/future), and 2
pending concession requests.

Idempotent: re-running the script does not duplicate rows. Lookup is by
natural key (code, email, roll_number, (program, year), (student, year)).

Run with:
    python -m app.db.seed
or
    python -m app.db.seed --reset   # truncate then reseed (dev only)

The script relies on the Alembic migration having created the tables. If you
run it against a fresh SQLite db (tests), `app.db.session` will be pointed
at the test db; call `Base.metadata.create_all(engine)` from the test
fixture first.
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.concession import Concession, ConcessionStatus
from app.models.department import Department, Program
from app.models.fee import (
    FeeHead,
    FeeStructure,
    FeeStructureLine,
    Installment,
    InstallmentStatus,
    StudentFeeAssignment,
)
from app.models.student import Student, StudentStatus
from app.models.user import Role, User

# Deterministic RNG so re-runs (and tests) are stable.
RNG = random.Random(424242)

PASSWORD = "Password123!"

# ── Domain seed data ────────────────────────────────────────────────
DEPARTMENTS = [
    ("CS", "Computer Science"),
    ("EE", "Electrical Engineering"),
    ("ME", "Mechanical Engineering"),
]

PROGRAMS = [
    ("BTECH-CS", "B.Tech Computer Science", "CS", 4),
    ("BTECH-EE", "B.Tech Electrical Engineering", "EE", 4),
    ("BTECH-ME", "B.Tech Mechanical Engineering", "ME", 4),
    ("MTECH-CS", "M.Tech Computer Science", "CS", 2),
]

FEE_HEADS = [
    ("TUITION", "Tuition Fee", "Core academic tuition", 10, False),
    ("LAB", "Laboratory Fee", "Lab maintenance", 20, False),
    ("LIBRARY", "Library Fee", "Library access", 30, False),
    ("EXAM", "Examination Fee", "Term-end examinations", 40, False),
    ("HOSTEL", "Hostel Fee", "Boarding", 50, True),
    ("MESS", "Mess Fee", "Food", 60, True),
]

ACADEMIC_YEAR = "2024-2025"

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Ananya", "Diya", "Ishaan", "Kabir", "Meera",
    "Riya", "Rohan", "Saanvi", "Arjun", "Navya", "Aryan", "Ira", "Krishna",
    "Maya", "Nikhil", "Pooja", "Rahul", "Sara", "Vikram", "Aisha", "Dhruv",
]
LAST_NAMES = [
    "Sharma", "Verma", "Iyer", "Nair", "Reddy", "Gupta", "Patel", "Singh",
    "Rao", "Khan", "Das", "Bose", "Menon", "Joshi", "Kapoor",
]


def _roll(i: int) -> str:
    return f"STU2024{i:04d}"


# ── Helpers ─────────────────────────────────────────────────────────
def _get_or_create(db: Session, model, defaults: dict, **keys):
    obj = db.execute(select(model).where(*[getattr(model, k) == v for k, v in keys.items()])).scalar_one_or_none()
    if obj:
        return obj, False
    obj = model(**keys, **defaults)
    db.add(obj)
    db.flush()
    return obj, True


def _bootstrap_admin(db: Session) -> User:
    admin, created = _get_or_create(
        db, User,
        defaults={
            "password_hash": hash_password(PASSWORD),
            "full_name": "System Admin",
            "role": Role.ADMIN,
            "is_active": True,
        },
        email="admin@edupay.college",
    )
    return admin


def _create_role_users(db: Session, admin_id: str) -> dict[str, User]:
    users = {}
    for role, name, email in [
        (Role.FINANCE_MANAGER, "Finance Manager", "manager@edupay.college"),
        (Role.FINANCE_STAFF, "Finance Staff", "staff@edupay.college"),
        (Role.STUDENT, "Demo Student", "student@edupay.college"),
    ]:
        u, _ = _get_or_create(
            db, User,
            defaults={
                "password_hash": hash_password(PASSWORD),
                "full_name": name,
                "role": role,
                "is_active": True,
            },
            email=email,
        )
        users[role.value] = u
    return users


def _seed_departments_programs(db: Session, admin_id: str) -> dict[str, str]:
    dept_ids: dict[str, str] = {}
    for code, name in DEPARTMENTS:
        d, _ = _get_or_create(
            db, Department,
            defaults={"name": name},
            code=code,
        )
        dept_ids[code] = d.id
    program_ids: dict[str, str] = {}
    for code, name, dept_code, dur in PROGRAMS:
        p, _ = _get_or_create(
            db, Program,
            defaults={
                "name": name,
                "department_id": dept_ids[dept_code],
                "duration_years": dur,
            },
            code=code,
        )
        program_ids[code] = p.id
    return program_ids


def _seed_fee_heads(db: Session, admin_id: str) -> dict[str, str]:
    head_ids: dict[str, str] = {}
    for code, name, desc, prio, refund in FEE_HEADS:
        h, _ = _get_or_create(
            db, FeeHead,
            defaults={
                "name": name,
                "description": desc,
                "priority": prio,
                "is_refundable": refund,
            },
            code=code,
        )
        head_ids[code] = h.id
    return head_ids


def _seed_fee_structures(db: Session, program_ids: dict[str, str], head_ids: dict[str, str], admin_id: str) -> dict[str, str]:
    """One active fee structure per program for ACADEMIC_YEAR."""
    # Different amounts per program to be realistic.
    base_amounts = {
        "BTECH-CS": Decimal("90000.00"),
        "BTECH-EE": Decimal("80000.00"),
        "BTECH-ME": Decimal("75000.00"),
        "MTECH-CS": Decimal("60000.00"),
    }
    # Head split fractions (must sum to 1.0)
    split = {
        "TUITION": Decimal("0.70"),
        "LAB": Decimal("0.08"),
        "LIBRARY": Decimal("0.04"),
        "EXAM": Decimal("0.05"),
        "HOSTEL": Decimal("0.08"),
        "MESS": Decimal("0.05"),
    }
    structure_ids: dict[str, str] = {}
    for pcode, pid in program_ids.items():
        total = base_amounts[pcode]
        fs, created = _get_or_create(
            db, FeeStructure,
            defaults={
                "effective_from": date(2024, 7, 1),
                "effective_to": date(2025, 6, 30),
                "is_active": True,
                "created_by": admin_id,
            },
            program_id=pid,
            academic_year=ACADEMIC_YEAR,
        )
        structure_ids[pcode] = fs.id
        if not created:
            continue
        for hcode, frac in split.items():
            amount = (total * frac).quantize(Decimal("0.01"))
            # Quantise round-up bias: ensure sum == total
            db.add(
                FeeStructureLine(
                    fee_structure_id=fs.id,
                    fee_head_id=head_ids[hcode],
                    amount=amount,
                )
            )
        db.flush()
        # Adjust last line so the sum exactly equals total (avoid 1-cent drift)
        lines = list(db.execute(
            select(FeeStructureLine).where(FeeStructureLine.fee_structure_id == fs.id)
        ).scalars().all())
        s = sum((ln.amount for ln in lines), Decimal("0.00"))
        diff = total - s
        if diff != 0:
            lines[-1].amount = lines[-1].amount + diff
        db.flush()
    return structure_ids


def _seed_students(
    db: Session,
    program_ids: dict[str, str],
    head_ids: dict[str, str],
    structure_ids: dict[str, str],
    admin_id: str,
    n: int = 300,
) -> tuple[list[tuple[Student, User]], list[Student]]:
    """Create n students + matching STUDENT-role users + fee assignments + installments."""
    program_codes = list(program_ids.keys())
    students: list[Student] = []
    pairs: list[tuple[Student, User]] = []

    # Today anchors for past/current/future due dates.
    today = date.today()
    past_1 = today - timedelta(days=120)
    past_2 = today - timedelta(days=30)
    future_1 = today + timedelta(days=60)
    # third installment is "future_1" — we want 3 installments: past, current (today-ish), future

    for i in range(1, n + 1):
        roll = _roll(i)
        # Idempotent: if student exists, fetch
        s = db.execute(select(Student).where(Student.roll_number == roll)).scalar_one_or_none()
        if s:
            students.append(s)
            continue
        pcode = program_codes[(i - 1) % len(program_codes)]
        fname = RNG.choice(FIRST_NAMES)
        lname = RNG.choice(LAST_NAMES)
        full = f"{fname} {lname}"
        email = f"{roll.lower()}@edupay.college"
        s = Student(
            roll_number=roll,
            full_name=full,
            email=email,
            phone=None,
            program_id=program_ids[pcode],
            batch_year=2024,
            status=StudentStatus.ACTIVE,
            created_by=admin_id,
        )
        db.add(s)
        db.flush()
        # Matching STUDENT-role user
        u = User(
            email=email,
            password_hash=hash_password(PASSWORD),
            full_name=full,
            role=Role.STUDENT,
            is_active=True,
            student_id=s.id,
        )
        db.add(u)
        db.flush()
        students.append(s)
        pairs.append((s, u))

        # Fee assignment + 3 installments (idempotent: skip if assignment exists)
        existing = db.execute(
            select(StudentFeeAssignment).where(
                StudentFeeAssignment.student_id == s.id,
                StudentFeeAssignment.academic_year == ACADEMIC_YEAR,
            )
        ).scalar_one_or_none()
        if existing:
            continue
        # Split total into 3 installments: 40% / 30% / 30%
        structure_id = structure_ids[pcode]
        total = db.execute(
            select(FeeStructureLine).where(FeeStructureLine.fee_structure_id == structure_id)
        ).scalars().all()
        total_invoiced = sum((ln.amount for ln in total), Decimal("0.00"))
        a1 = (total_invoiced * Decimal("0.40")).quantize(Decimal("0.01"))
        a2 = (total_invoiced * Decimal("0.30")).quantize(Decimal("0.01"))
        a3 = total_invoiced - a1 - a2  # exact
        assignment = StudentFeeAssignment(
            student_id=s.id,
            fee_structure_id=structure_id,
            academic_year=ACADEMIC_YEAR,
            total_invoiced=total_invoiced,
            created_by=admin_id,
        )
        db.add(assignment)
        db.flush()
        for num, (amt, due) in enumerate(
            [
                (a1, past_1),
                (a2, past_2),
                (a3, future_1),
            ],
            start=1,
        ):
            # Cached status: installments past due and unpaid → OVERDUE
            cached = InstallmentStatus.OVERDUE if due < today else InstallmentStatus.PENDING
            db.add(
                Installment(
                    student_fee_assignment_id=assignment.id,
                    installment_number=num,
                    due_date=due,
                    amount=amt,
                    fee_head_id=None,  # composite installment
                    status=cached,
                    created_by=admin_id,
                )
            )
    db.flush()
    return pairs, students


def _seed_concessions(db: Session, students: list[Student], admin_id: str) -> None:
    """Create 2 pending concession requests."""
    head_tuition = db.execute(select(FeeHead).where(FeeHead.code == "TUITION")).scalar_one()
    existing = db.execute(select(Concession).where(Concession.status == ConcessionStatus.PENDING)).scalars().all()
    if len(existing) >= 2:
        return
    need = 2 - len(existing)
    picked = students[:need]
    for s in picked:
        # Attach to first installment of this student
        inst = db.execute(
            select(Installment)
            .join(StudentFeeAssignment, StudentFeeAssignment.id == Installment.student_fee_assignment_id)
            .where(StudentFeeAssignment.student_id == s.id)
            .order_by(Installment.installment_number)
            .limit(1)
        ).scalar_one_or_none()
        db.add(
            Concession(
                student_id=s.id,
                fee_head_id=head_tuition.id,
                installment_id=inst.id if inst else None,
                amount=Decimal("5000.00"),
                reason="Merit concession request — pending approval",
                status=ConcessionStatus.PENDING,
                approved_by=None,
                approved_at=None,
                created_by=admin_id,
            )
        )
    db.flush()


def run(reset: bool = False) -> None:
    from app.core.logging import setup_logging
    setup_logging("INFO")
    from app.core.logging import get_logger
    log = get_logger(__name__)

    if reset:
        log.warning("seed.reset", extra={"note": "dropping all tables and recreating"})
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        admin = _bootstrap_admin(db)
        db.flush()
        admin_id = admin.id
        log.info("seed.admin", extra={"admin_id": admin_id, "email": admin.email})

        _create_role_users(db, admin_id)
        program_ids = _seed_departments_programs(db, admin_id)
        head_ids = _seed_fee_heads(db, admin_id)
        structure_ids = _seed_fee_structures(db, program_ids, head_ids, admin_id)
        _, students = _seed_students(db, program_ids, head_ids, structure_ids, admin_id, n=300)
        _seed_concessions(db, students, admin_id)

        db.commit()
        # Final counts for the log line
        counts = {
            "users": db.execute(select(User)).scalars().all().__len__(),
            "students": db.execute(select(Student)).scalars().all().__len__(),
            "fee_heads": db.execute(select(FeeHead)).scalars().all().__len__(),
            "fee_structures": db.execute(select(FeeStructure)).scalars().all().__len__(),
            "assignments": db.execute(select(StudentFeeAssignment)).scalars().all().__len__(),
            "installments": db.execute(select(Installment)).scalars().all().__len__(),
            "concessions_pending": db.execute(
                select(Concession).where(Concession.status == ConcessionStatus.PENDING)
            ).scalars().all().__len__(),
        }
        log.info("seed.done", extra={"counts": counts})
        print("SEED COMPLETE:", counts)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="EduPay seed script v1")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables before seeding (dev only)")
    args = parser.parse_args()
    run(reset=args.reset)


if __name__ == "__main__":
    main()
