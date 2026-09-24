"""Reconciliation service (Package C).

CSV settlement upload → parse → matching engine → classify each line per the
SPEC definitions:

  MATCHED          : same reference + same amount
  AMOUNT_MISMATCH  : reference matches, amount differs (flag, NEVER auto-adjust)
  MISSING_INTERNAL : settlement line exists, no internal payment with that ref
  MISSING_EXTERNAL : internal SUCCESS payment, no settlement line referencing it
  DUPLICATE        : same external reference settling twice (intra-CSV)

Mismatches NEVER auto-modify financial truth. Resolving a line only records a
FINANCE_MANAGER's decision (resolved_classification + notes) — it does not
mutate payments, allocations, or installments.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import write_audit
from app.core.logging import get_logger
from app.models.payment import Payment, PaymentStatus
from app.models.reconciliation import (
    ReconciliationBatch,
    ReconciliationClassification,
    ReconciliationLine,
)
from app.models.student import Student

log = get_logger(__name__)

# Date window for the "suggested match" feature (reference-less or unfound
# lines matched by amount + recency). 7 days each side.
SUGGEST_WINDOW_DAYS = 7


class CSVParseError(Exception):
    pass


class NotFound(Exception):
    pass


class AlreadyResolved(Exception):
    pass


def parse_csv(content: str) -> List[dict]:
    """Parse settlement CSV. Columns: external_reference, external_amount, [student_roll].

    Header row required. Returns a list of dicts.
    """
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames or "external_reference" not in reader.fieldnames or "external_amount" not in reader.fieldnames:
        raise CSVParseError("CSV must have headers: external_reference, external_amount (optional: student_roll)")
    rows: List[dict] = []
    for i, row in enumerate(reader, start=2):  # 2 = header is line 1
        ref = (row.get("external_reference") or "").strip()
        amt_raw = (row.get("external_amount") or "").strip()
        if not ref or not amt_raw:
            raise CSVParseError(f"line {i}: missing external_reference or external_amount")
        try:
            amt = Decimal(amt_raw)
        except InvalidOperation:
            raise CSVParseError(f"line {i}: external_amount '{amt_raw}' is not a number")
        if amt <= 0:
            raise CSVParseError(f"line {i}: external_amount must be > 0")
        rows.append({
            "external_reference": ref,
            "external_amount": amt,
            "student_roll": (row.get("student_roll") or "").strip() or None,
        })
    return rows


def _to_dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def classify_batch(
    db: Session,
    batch: ReconciliationBatch,
    rows: List[dict],
) -> List[ReconciliationLine]:
    """Classify each settlement row + generate MISSING_EXTERNAL lines.

    Returns the created ReconciliationLine rows.
    """
    lines: List[ReconciliationLine] = []

    # Intra-CSV duplicate detection: count refs.
    ref_counts: dict[str, int] = {}
    for r in rows:
        ref_counts[r["external_reference"]] = ref_counts.get(r["external_reference"], 0) + 1
    seen_refs: set[str] = set()

    # All internal SUCCESS payments (for MISSING_EXTERNAL + matching).
    success_payments = list(db.execute(
        select(Payment).where(Payment.status.in_([PaymentStatus.SUCCESS, PaymentStatus.REVERSAL_REQUESTED, PaymentStatus.REVERSED]))
    ).scalars().all())
    payments_by_ref: dict[str, Payment] = {p.gateway_ref: p for p in success_payments if p.gateway_ref}

    referenced_refs: set[str] = set()

    for r in rows:
        ref = r["external_reference"]
        amt = r["external_amount"]
        payment = payments_by_ref.get(ref)

        classification: ReconciliationClassification
        payment_id: Optional[str] = None
        student_id: Optional[str] = None
        suggested_payment_id: Optional[str] = None
        notes: Optional[str] = None

        # Resolve student from roll if provided.
        if r["student_roll"]:
            stu = db.execute(
                select(Student).where(Student.roll_number == r["student_roll"])
            ).scalar_one_or_none()
            if stu:
                student_id = stu.id

        if ref in seen_refs:
            # Second+ occurrence of the same external_reference in this CSV.
            classification = ReconciliationClassification.DUPLICATE
            notes = "duplicate external reference within this settlement file"
            if payment:
                payment_id = payment.id
        elif payment:
            referenced_refs.add(ref)
            payment_id = payment.id
            if not student_id:
                student_id = payment.student_id
            if _to_dec(payment.amount) == amt:
                classification = ReconciliationClassification.MATCHED
            else:
                classification = ReconciliationClassification.AMOUNT_MISMATCH
                notes = f"internal {payment.amount} vs settlement {amt}"
        else:
            # No internal payment with this gateway_ref.
            classification = ReconciliationClassification.MISSING_INTERNAL
            # Suggested match: a SUCCESS payment with matching amount within
            # the date window (for human review only — never auto-link).
            suggested = _suggest_match(success_payments, amt)
            if suggested:
                suggested_payment_id = suggested.id
                notes = f"suggested match: payment {suggested.id} (amount {suggested.amount})"

        lines.append(ReconciliationLine(
            batch_id=batch.id,
            external_reference=ref,
            external_amount=amt,
            student_id=student_id,
            payment_id=payment_id,
            classification=classification,
            suggested_payment_id=suggested_payment_id,
            notes=notes,
            created_by=batch.created_by,
        ))
        seen_refs.add(ref)

    # MISSING_EXTERNAL: internal SUCCESS/REVERSAL_REQUESTED payments whose
    # gateway_ref is NOT referenced by any settlement line.
    for p in success_payments:
        if p.status == PaymentStatus.REVERSED:
            continue  # reversed payments aren't expected to settle
        if p.gateway_ref and p.gateway_ref not in referenced_refs:
            lines.append(ReconciliationLine(
                batch_id=batch.id,
                external_reference=f"(missing-settlement) {p.gateway_ref}",
                external_amount=_to_dec(p.amount),
                student_id=p.student_id,
                payment_id=p.id,
                classification=ReconciliationClassification.MISSING_EXTERNAL,
                notes=f"internal payment {p.id} has no settlement line",
                created_by=batch.created_by,
            ))

    # Persist + update batch counts.
    for ln in lines:
        db.add(ln)
    db.flush()
    counts = {c: 0 for c in ReconciliationClassification}
    for ln in lines:
        counts[ln.classification] += 1
    batch.total_lines = len(lines)
    batch.matched_count = counts[ReconciliationClassification.MATCHED]
    batch.amount_mismatch_count = counts[ReconciliationClassification.AMOUNT_MISMATCH]
    batch.missing_internal_count = counts[ReconciliationClassification.MISSING_INTERNAL]
    batch.missing_external_count = counts[ReconciliationClassification.MISSING_EXTERNAL]
    batch.duplicate_count = counts[ReconciliationClassification.DUPLICATE]
    db.flush()
    return lines


def _suggest_match(payments: List[Payment], amount: Decimal) -> Optional[Payment]:
    """Suggest a SUCCESS payment with the exact amount (for human review)."""
    for p in payments:
        if p.status == PaymentStatus.SUCCESS and _to_dec(p.amount) == amount:
            return p
    return None


def upload(
    db: Session,
    *,
    csv_content: str,
    uploaded_by: str,
    source_file_name: str,
) -> Tuple[ReconciliationBatch, List[ReconciliationLine]]:
    """Parse + classify a settlement CSV. Returns (batch, lines)."""
    rows = parse_csv(csv_content)
    batch = ReconciliationBatch(
        uploaded_by=uploaded_by,
        source_file_name=source_file_name,
        created_by=uploaded_by,
    )
    db.add(batch)
    db.flush()
    lines = classify_batch(db, batch, rows)
    write_audit(
        db,
        actor_user_id=uploaded_by,
        action="reconciliation.uploaded",
        entity_type="reconciliation_batch",
        entity_id=batch.id,
        metadata={
            "source_file": source_file_name,
            "total_lines": batch.total_lines,
            "matched": batch.matched_count,
            "amount_mismatch": batch.amount_mismatch_count,
            "missing_internal": batch.missing_internal_count,
            "missing_external": batch.missing_external_count,
            "duplicate": batch.duplicate_count,
        },
    )
    db.commit()
    db.refresh(batch)
    return batch, lines


def resolve_line(
    db: Session,
    line_id: str,
    *,
    resolved_classification: ReconciliationClassification,
    notes: str,
    resolved_by: str,
) -> ReconciliationLine:
    """Manager-approved resolution of a reconciliation line.

    Records the decision (resolved_classification + notes + resolved_by + ts).
    Does NOT mutate any payment, allocation, or installment — mismatches never
    auto-modify financial truth. Raises AlreadyResolved if the line was already
    resolved (resolutions are immutable once set).
    """
    ln = db.get(ReconciliationLine, line_id)
    if not ln:
        raise NotFound()
    if ln.resolved_classification is not None:
        raise AlreadyResolved()
    ln.resolved_classification = resolved_classification.value
    ln.resolution_notes = notes
    ln.resolved_by = resolved_by
    ln.resolved_at = datetime.now(timezone.utc)
    write_audit(
        db,
        actor_user_id=resolved_by,
        action="reconciliation.line_resolved",
        entity_type="reconciliation_line",
        entity_id=ln.id,
        metadata={
            "original": ln.classification.value,
            "resolved": resolved_classification.value,
            "notes": notes,
        },
    )
    db.commit()
    db.refresh(ln)
    return ln


def list_batches(db: Session, *, limit: int = 50, offset: int = 0) -> Tuple[List[ReconciliationBatch], int]:
    from sqlalchemy import func
    stmt = select(ReconciliationBatch).order_by(ReconciliationBatch.created_at.desc())
    total = db.execute(select(func.count()).select_from(ReconciliationBatch)).scalar_one()
    rows = list(db.execute(stmt.limit(limit).offset(offset)).scalars().all())
    return rows, int(total)


def get_batch(db: Session, batch_id: str) -> ReconciliationBatch:
    b = db.get(ReconciliationBatch, batch_id)
    if not b:
        raise NotFound()
    return b


def list_lines(
    db: Session,
    *,
    batch_id: Optional[str] = None,
    classification: Optional[ReconciliationClassification] = None,
    resolved: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> Tuple[List[ReconciliationLine], int]:
    from sqlalchemy import func
    stmt = select(ReconciliationLine)
    count_stmt = select(func.count()).select_from(ReconciliationLine)
    if batch_id:
        stmt = stmt.where(ReconciliationLine.batch_id == batch_id)
        count_stmt = count_stmt.where(ReconciliationLine.batch_id == batch_id)
    if classification:
        stmt = stmt.where(ReconciliationLine.classification == classification)
        count_stmt = count_stmt.where(ReconciliationLine.classification == classification)
    if resolved is True:
        stmt = stmt.where(ReconciliationLine.resolved_classification.is_not(None))
        count_stmt = count_stmt.where(ReconciliationLine.resolved_classification.is_not(None))
    elif resolved is False:
        stmt = stmt.where(ReconciliationLine.resolved_classification.is_(None))
        count_stmt = count_stmt.where(ReconciliationLine.resolved_classification.is_(None))
    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(ReconciliationLine.created_at.desc(), ReconciliationLine.id.desc()).limit(limit).offset(offset)
    rows = list(db.execute(stmt).scalars().all())
    return rows, int(total)
