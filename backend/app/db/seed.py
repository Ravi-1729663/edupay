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


def _seed_payments_v2(db: Session, students: list[Student], admin_id: str) -> dict:
    """Seed v2: one of each payment state + a duplicate-attempt.

    Creates:
      - 1 SUCCESS cash (counter) payment → allocated
      - 1 SUCCESS online payment (via simulated webhook callback) → allocated
      - 1 FAILED online payment
      - 1 PENDING online payment (stuck — no callback)
      - 1 UNKNOWN online payment (verify timed out)
      - 1 DUPLICATE attempt: second call with same idempotency_key → rejected
        (so only one record exists; the second is a no-op)

    Idempotent: checks by idempotency_key.
    """
    from app.models.payment import (
        Payment,
        PaymentAllocation,
        PaymentMethod,
        PaymentStatus,
    )
    from app.services import payment_service, gateway_service

    staff = db.execute(select(User).where(User.email == "staff@edupay.college")).scalar_one()
    tuition = db.execute(select(FeeHead).where(FeeHead.code == "TUITION")).scalar_one()

    def _existing(key: str) -> bool:
        return db.execute(
            select(Payment).where(Payment.idempotency_key == key)
        ).scalar_one_or_none() is not None

    counts = {"created": 0, "duplicate_rejected": 0}

    # Pick 6 students for the 6 payment scenarios.
    picked = students[:6]

    def _installment_for(student_id: str):
        return db.execute(
            select(Installment)
            .join(StudentFeeAssignment, StudentFeeAssignment.id == Installment.student_fee_assignment_id)
            .where(StudentFeeAssignment.student_id == student_id)
            .order_by(Installment.due_date, Installment.installment_number)
            .limit(1)
        ).scalar_one()

    # 1. SUCCESS cash counter payment for student[0]
    key = "seed-cash-success"
    if not _existing(key):
        p = payment_service.create_counter_payment(
            db,
            student_id=picked[0].id,
            amount=Decimal("1000.00"),
            method=PaymentMethod.CASH,
            idempotency_key=key,
            initiated_by=staff.id,
        )
        counts["created"] += 1

    # 2. SUCCESS online payment for student[1] — simulate the gateway callback.
    key = "seed-online-success"
    if not _existing(key):
        p, gref, _ = payment_service.initiate_online_payment(
            db,
            student_id=picked[1].id,
            amount=Decimal("2000.00"),
            idempotency_key=key,
            initiated_by=staff.id,
        )
        # Record the true outcome + apply the webhook synchronously.
        gateway_service.record_true_outcome(gref, "SUCCESS")
        payment_service.apply_webhook_callback(
            db, gref, PaymentStatus.SUCCESS, Decimal("2000.00"), actor_id=staff.id
        )
        counts["created"] += 1

    # 3. FAILED online payment for student[2]
    key = "seed-online-failed"
    if not _existing(key):
        p, gref, _ = payment_service.initiate_online_payment(
            db,
            student_id=picked[2].id,
            amount=Decimal("3000.00"),
            idempotency_key=key,
            initiated_by=staff.id,
        )
        gateway_service.record_true_outcome(gref, "FAILED")
        payment_service.apply_webhook_callback(
            db, gref, PaymentStatus.FAILED, Decimal("3000.00"), actor_id=staff.id
        )
        counts["created"] += 1

    # 4. PENDING online payment (stuck — no callback ever fires)
    key = "seed-online-pending"
    if not _existing(key):
        p, gref, _ = payment_service.initiate_online_payment(
            db,
            student_id=picked[3].id,
            amount=Decimal("4000.00"),
            idempotency_key=key,
            initiated_by=staff.id,
        )
        # Do NOT record an outcome; do NOT fire a callback. Stays PENDING.
        counts["created"] += 1

    # 5. UNKNOWN online payment (verify timed out)
    key = "seed-online-unknown"
    if not _existing(key):
        p, gref, _ = payment_service.initiate_online_payment(
            db,
            student_id=picked[4].id,
            amount=Decimal("5000.00"),
            idempotency_key=key,
            initiated_by=staff.id,
        )
        gateway_service.record_true_outcome(gref, "SUCCESS")  # truth: succeeded
        # Verify → PENDING becomes UNKNOWN (we don't resolve here; tests will).
        payment_service.verify_payment(db, p.id, staff.id)
        counts["created"] += 1

    # 6. DUPLICATE attempt: try to initiate with the same idempotency_key as #1.
    key = "seed-cash-success"
    try:
        payment_service.create_counter_payment(
            db,
            student_id=picked[5].id,
            amount=Decimal("99999.00"),
            method=PaymentMethod.CASH,
            idempotency_key=key,
            initiated_by=staff.id,
        )
    except payment_service.IdempotencyConflict:
        counts["duplicate_rejected"] += 1
        db.rollback()

    db.commit()
    # Recompute installment statuses for the seeded payments.
    for s in picked[:3]:  # only the first 3 (SUCCESS ones) have allocations
        inst = _installment_for(s.id)
        if inst:
            payment_service._refresh_installment_status(db, inst)
    db.commit()
    return counts


def _seed_reconciliation_v3(db: Session, students: list[Student], admin_id: str) -> dict:
    """Seed v3: a reconciliation batch with one line of EACH classification
    (MATCHED, AMOUNT_MISMATCH, MISSING_INTERNAL, MISSING_EXTERNAL, DUPLICATE)
    + a reversed payment (SUCCESS → reversal-request → reversal-complete).

    Idempotent: checks by source_file_name + idempotency keys.
    """
    from app.models.payment import Payment, PaymentMethod, PaymentStatus
    from app.models.reconciliation import ReconciliationBatch, ReconciliationClassification
    from app.services import gateway_service, payment_service, reconciliation_service

    staff = db.execute(select(User).where(User.email == "staff@edupay.college")).scalar_one()
    mgr = db.execute(select(User).where(User.email == "manager@edupay.college")).scalar_one()

    counts = {"reversed_payment": 0, "recon_batch_lines": 0}

    # ── A reversed payment ───────────────────────────────────────────
    # Pick a student we haven't used for the v2 payments (students[5] was the
    # duplicate-attempt target; use students[6] here).
    rev_student = students[6] if len(students) > 6 else students[-1]
    rev_key = "seed-reversed-success"
    existing_rev = db.execute(
        select(Payment).where(Payment.idempotency_key == rev_key)
    ).scalar_one_or_none()
    if existing_rev is None:
        p = payment_service.create_counter_payment(
            db,
            student_id=rev_student.id,
            amount=Decimal("700.00"),
            method=PaymentMethod.CASH,
            idempotency_key=rev_key,
            initiated_by=staff.id,
        )
        rev = payment_service.request_reversal(db, p.id, Decimal("700.00"), "seed v3 reversal demo", staff.id)
        payment_service.complete_reversal(db, rev.id, mgr.id)
        counts["reversed_payment"] += 1
    else:
        counts["reversed_payment"] += 1  # already exists

    # ── A reconciliation batch with one of each classification ────────
    source_name = "seed-recon-v3.csv"
    existing_batch = db.execute(
        select(ReconciliationBatch).where(ReconciliationBatch.source_file_name == source_name)
    ).scalar_one_or_none()
    if existing_batch is None:
        # We need THREE SUCCESS online payments with distinct gateway_refs to
        # exercise MATCHED, AMOUNT_MISMATCH, and MISSING_EXTERNAL:
        #   - Payment A (v2 online-success): ref_A, amount 2000  → MATCHED
        #   - Payment B (new): ref_B, amount 123  → AMOUNT_MISMATCH (CSV says 999)
        #   - Payment C (new): ref_C, amount 456  → MISSING_EXTERNAL (not in CSV)
        online_succ = db.execute(
            select(Payment).where(Payment.idempotency_key == "seed-online-success")
        ).scalar_one()
        ref_a = online_succ.gateway_ref
        amt_a = str(online_succ.amount)

        # Payment B for AMOUNT_MISMATCH.
        key_b = "seed-recon-amt-mismatch"
        if db.execute(select(Payment).where(Payment.idempotency_key == key_b)).scalar_one_or_none() is None:
            _, gref_b, _ = payment_service.initiate_online_payment(
                db,
                student_id=(students[8] if len(students) > 8 else students[-1]).id,
                amount=Decimal("123.00"),
                idempotency_key=key_b,
                initiated_by=staff.id,
            )
            gateway_service.record_true_outcome(gref_b, "SUCCESS")
            payment_service.apply_webhook_callback(db, gref_b, PaymentStatus.SUCCESS, Decimal("123.00"), staff.id)
        p_b = db.execute(select(Payment).where(Payment.idempotency_key == key_b)).scalar_one()
        ref_b = p_b.gateway_ref

        # Payment C for MISSING_EXTERNAL (NOT referenced in the CSV).
        key_c = "seed-recon-missing-external"
        if db.execute(select(Payment).where(Payment.idempotency_key == key_c)).scalar_one_or_none() is None:
            _, gref_c, _ = payment_service.initiate_online_payment(
                db,
                student_id=(students[9] if len(students) > 9 else students[-1]).id,
                amount=Decimal("456.00"),
                idempotency_key=key_c,
                initiated_by=staff.id,
            )
            gateway_service.record_true_outcome(gref_c, "SUCCESS")
            payment_service.apply_webhook_callback(db, gref_c, PaymentStatus.SUCCESS, Decimal("456.00"), staff.id)

        # CSV:
        #   ref_a, amt_a          → MATCHED
        #   ref_b, 999.00         → AMOUNT_MISMATCH (ref matches B but amount differs)
        #   missing_ref, 999.00   → MISSING_INTERNAL (no internal payment)
        #   missing_ref, 999.00   → DUPLICATE (2nd occurrence of missing_ref)
        missing_ref = "SETTLEMENT-NO-INTERNAL-REF"
        csv_content = (
            "external_reference,external_amount,student_roll\n"
            f"{ref_a},{amt_a},\n"
            f"{ref_b},999.00,\n"
            f"{missing_ref},999.00,\n"
            f"{missing_ref},999.00,\n"
        )
        # Payment C is deliberately NOT in the CSV → MISSING_EXTERNAL.

        batch, lines = reconciliation_service.upload(
            db, csv_content=csv_content, uploaded_by=mgr.id, source_file_name=source_name
        )
        counts["recon_batch_lines"] = len(lines)
    else:
        # Already seeded; just count existing lines.
        from app.models.reconciliation import ReconciliationLine
        lines = list(db.execute(
            select(ReconciliationLine).where(ReconciliationLine.batch_id == existing_batch.id)
        ).scalars().all())
        counts["recon_batch_lines"] = len(lines)

    db.commit()
    return counts


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
        payments_v2 = _seed_payments_v2(db, students, admin_id)
        recon_v3 = _seed_reconciliation_v3(db, students, admin_id)

        db.commit()
        # Final counts for the log line
        from app.models.payment import Payment, PaymentStatus as PS
        from app.models.reconciliation import ReconciliationLine, ReconciliationBatch
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
            "payments_total": db.execute(select(Payment)).scalars().all().__len__(),
            "payments_success": db.execute(select(Payment).where(Payment.status == PS.SUCCESS)).scalars().all().__len__(),
            "payments_failed": db.execute(select(Payment).where(Payment.status == PS.FAILED)).scalars().all().__len__(),
            "payments_pending": db.execute(select(Payment).where(Payment.status == PS.PENDING)).scalars().all().__len__(),
            "payments_unknown": db.execute(select(Payment).where(Payment.status == PS.UNKNOWN)).scalars().all().__len__(),
            "payments_reversed": db.execute(select(Payment).where(Payment.status == PS.REVERSED)).scalars().all().__len__(),
            "payments_v2": payments_v2,
            "recon_batches": db.execute(select(ReconciliationBatch)).scalars().all().__len__(),
            "recon_lines": db.execute(select(ReconciliationLine)).scalars().all().__len__(),
            "recon_v3": recon_v3,
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
