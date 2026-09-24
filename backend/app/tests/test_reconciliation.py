"""Package C tests: reconciliation classifications + resolution workflow + reversals.

Required cases (per the brief):
  - all 5 classifications present (MATCHED, AMOUNT_MISMATCH, MISSING_INTERNAL,
    MISSING_EXTERNAL, DUPLICATE)
  - unauthorized resolution rejected (FINANCE_STAFF cannot resolve)
  - reversal of already-reversed payment rejected
  - outstanding correctly restored after a reversal
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.reconciliation import ReconciliationClassification, ReconciliationLine
from app.models.student import Student
from app.models.user import User
from app.services import gateway_service, payment_service, reconciliation_service
from app.tests.conftest import auth_header, login


# ── All 5 classifications ───────────────────────────────────────────
def test_all_five_classifications_present(client: TestClient) -> None:
    """The seed v3 batch contains one line of each classification."""
    mgr = login(client, "FINANCE_MANAGER")
    r = client.get("/reconciliation/lines?limit=200", headers=auth_header(mgr))
    assert r.status_code == 200
    lines = r.json()["items"]
    classes = {ln["classification"] for ln in lines}
    assert "MATCHED" in classes
    assert "AMOUNT_MISMATCH" in classes
    assert "MISSING_INTERNAL" in classes
    assert "MISSING_EXTERNAL" in classes
    assert "DUPLICATE" in classes


def test_upload_classifies_correctly(client: TestClient) -> None:
    """Upload a fresh CSV and verify each line gets the right classification."""
    mgr = login(client, "FINANCE_MANAGER")
    db = SessionLocal()
    try:
        # Find the seeded v2 online-success payment (ref + amount known).
        succ = db.execute(
            select(Payment).where(Payment.idempotency_key == "seed-online-success")
        ).scalar_one()
        ref = succ.gateway_ref
        amt = str(succ.amount)
        # A second SUCCESS payment for AMOUNT_MISMATCH (unique ref).
        s = db.execute(select(Student).order_by(Student.roll_number.desc()).limit(1)).scalar_one()
        staff = db.execute(select(User).where(User.email == "staff@edupay.college")).scalar_one()
        p, gref_b, _ = payment_service.initiate_online_payment(
            db, student_id=s.id, amount=Decimal("111.00"),
            idempotency_key="recon-upload-mismatch-" + s.roll_number,
            initiated_by=staff.id,
        )
        gateway_service.record_true_outcome(gref_b, "SUCCESS")
        payment_service.apply_webhook_callback(db, gref_b, PaymentStatus.SUCCESS, Decimal("111.00"), staff.id)
        # A third SUCCESS payment for MISSING_EXTERNAL (not in CSV).
        p2, gref_c, _ = payment_service.initiate_online_payment(
            db, student_id=s.id, amount=Decimal("222.00"),
            idempotency_key="recon-upload-missing-ext-" + s.roll_number,
            initiated_by=staff.id,
        )
        gateway_service.record_true_outcome(gref_c, "SUCCESS")
        payment_service.apply_webhook_callback(db, gref_c, PaymentStatus.SUCCESS, Decimal("222.00"), staff.id)
        ref_b = gref_b
    finally:
        db.close()

    csv_content = (
        "external_reference,external_amount,student_roll\n"
        f"{ref},{amt},\n"                      # MATCHED
        f"{ref_b},999.00,\n"                   # AMOUNT_MISMATCH
        "NO-SUCH-REF,999.00,\n"                # MISSING_INTERNAL
        "NO-SUCH-REF,999.00,\n"                # DUPLICATE
    )
    files = {"file": ("test.csv", csv_content, "text/csv")}
    r = client.post("/reconciliation/upload", files=files, headers=auth_header(mgr))
    assert r.status_code == 201, r.text
    body = r.json()
    lines = body["lines"]
    classes = {ln["classification"] for ln in lines}
    assert "MATCHED" in classes
    assert "AMOUNT_MISMATCH" in classes
    assert "MISSING_INTERNAL" in classes
    assert "DUPLICATE" in classes
    assert "MISSING_EXTERNAL" in classes  # auto-generated for gref_c


def test_csv_parse_errors(client: TestClient) -> None:
    """Bad CSVs are rejected with 422."""
    mgr = login(client, "FINANCE_MANAGER")
    # Missing header.
    r = client.post(
        "/reconciliation/upload",
        files={"file": ("bad.csv", "foo,bar\n1,2\n", "text/csv")},
        headers=auth_header(mgr),
    )
    assert r.status_code == 422
    # Negative amount.
    r = client.post(
        "/reconciliation/upload",
        files={"file": ("bad2.csv", "external_reference,external_amount\nR,-5\n", "text/csv")},
        headers=auth_header(mgr),
    )
    assert r.status_code == 422


# ── Unauthorized resolution rejected ───────────────────────────────
def test_staff_cannot_resolve_line(client: TestClient) -> None:
    """FINANCE_STAFF cannot resolve a reconciliation line (manager/admin only)."""
    staff_token = login(client, "FINANCE_STAFF")
    mgr_token = login(client, "FINANCE_MANAGER")
    # Find an unresolved line.
    mgr_r = client.get("/reconciliation/lines?resolved=false&limit=10", headers=auth_header(mgr_token))
    assert mgr_r.status_code == 200
    lines = mgr_r.json()["items"]
    assert len(lines) > 0
    line_id = lines[0]["id"]
    body = {"resolved_classification": "MATCHED", "notes": "manager accepted"}
    r = client.post(
        f"/reconciliation/lines/{line_id}/resolve",
        json=body,
        headers=auth_header(staff_token),
    )
    assert r.status_code == 403


def test_manager_can_resolve_line(client: TestClient) -> None:
    mgr = login(client, "FINANCE_MANAGER")
    # Find an unresolved AMOUNT_MISMATCH line.
    r = client.get("/reconciliation/lines?classification=AMOUNT_MISMATCH&limit=10", headers=auth_header(mgr))
    lines = r.json()["items"]
    assert len(lines) > 0
    line = lines[0]
    assert line["resolved_classification"] is None
    body = {"resolved_classification": "AMOUNT_MISMATCH", "notes": "fee difference accepted"}
    r = client.post(f"/reconciliation/lines/{line['id']}/resolve", json=body, headers=auth_header(mgr))
    assert r.status_code == 200
    assert r.json()["resolved_classification"] == "AMOUNT_MISMATCH"
    assert r.json()["resolved_by"] is not None


def test_resolution_is_immutable(client: TestClient) -> None:
    """A resolved line cannot be resolved again (409)."""
    mgr = login(client, "FINANCE_MANAGER")
    # Resolve a line first.
    r = client.get("/reconciliation/lines?classification=DUPLICATE&limit=10", headers=auth_header(mgr))
    lines = r.json()["items"]
    assert len(lines) > 0
    line_id = lines[0]["id"]
    body = {"resolved_classification": "DUPLICATE", "notes": "keep first"}
    r1 = client.post(f"/reconciliation/lines/{line_id}/resolve", json=body, headers=auth_header(mgr))
    assert r1.status_code == 200
    # Resolve again → 409.
    r2 = client.post(f"/reconciliation/lines/{line_id}/resolve", json=body, headers=auth_header(mgr))
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "already_resolved"


def test_resolution_does_not_mutate_financial_truth(client: TestClient) -> None:
    """Resolving a line never creates/updates a payment or allocation."""
    mgr = login(client, "FINANCE_MANAGER")
    db = SessionLocal()
    try:
        before_payments = db.execute(select(Payment)).scalars().all().__len__()
        from app.models.payment import PaymentAllocation
        before_allocs = db.execute(select(PaymentAllocation)).scalars().all().__len__()
    finally:
        db.close()
    # Resolve any unresolved line.
    r = client.get("/reconciliation/lines?resolved=false&limit=5", headers=auth_header(mgr))
    lines = r.json()["items"]
    assert len(lines) > 0
    line_id = lines[0]["id"]
    body = {"resolved_classification": "MISSING_INTERNAL", "notes": "investigated"}
    r = client.post(f"/reconciliation/lines/{line_id}/resolve", json=body, headers=auth_header(mgr))
    assert r.status_code == 200
    db = SessionLocal()
    try:
        after_payments = db.execute(select(Payment)).scalars().all().__len__()
        after_allocs = db.execute(select(PaymentAllocation)).scalars().all().__len__()
    finally:
        db.close()
    assert after_payments == before_payments, "resolution must not create payments"
    assert after_allocs == before_allocs, "resolution must not create allocations"


# ── Reversal of already-reversed payment rejected ───────────────────
def test_reversal_of_already_reversed_rejected(client: TestClient) -> None:
    """A payment that is already REVERSED cannot be reversal-requested again."""
    mgr = login(client, "FINANCE_MANAGER")
    db = SessionLocal()
    try:
        # Find the seeded reversed payment.
        rev_p = db.execute(
            select(Payment).where(Payment.status == PaymentStatus.REVERSED).limit(1)
        ).scalar_one()
        pid = rev_p.id
    finally:
        db.close()
    body = {"amount": "1.00", "reason": "second attempt"}
    r = client.post(f"/payments/{pid}/reversal-request", json=body, headers=auth_header(mgr))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


# ── Outstanding correctly restored after reversal ───────────────────
def test_outstanding_restored_for_reversed_payment(client: TestClient) -> None:
    """The seeded reversed payment's installment outstanding equals the
    invoiced amount (allocations from a REVERSED payment are voided)."""
    db = SessionLocal()
    try:
        rev_p = db.execute(
            select(Payment).where(Payment.status == PaymentStatus.REVERSED).limit(1)
        ).scalar_one()
        # Find its allocations (still exist, but excluded from outstanding).
        from app.models.payment import PaymentAllocation
        allocs = db.execute(
            select(PaymentAllocation).where(PaymentAllocation.payment_id == rev_p.id)
        ).scalars().all()
        assert len(allocs) >= 1, "reversed payment should have allocations (now voided)"
        inst_id = allocs[0].installment_id
        outstanding = payment_service._installment_outstanding(db, inst_id)
        from app.models.fee import Installment
        inst = db.get(Installment, inst_id)
        # Outstanding should equal the full installment amount (reversal restored it).
        assert outstanding == Decimal(inst.amount), (
            f"reversal should restore outstanding to {inst.amount}, got {outstanding}"
        )
    finally:
        db.close()


def test_integrity_zero_drift_with_recon_and_reversals(client: TestClient) -> None:
    """Integrity checker still zero-drift after seed v3 (recon + reversed payment)."""
    mgr = login(client, "FINANCE_MANAGER")
    r = client.get("/admin/integrity-check", headers=auth_header(mgr))
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True, f"drifts={body['drifts']} violations={body['invariant_violations']}"
    assert body["payments_checked"] >= 8  # 8 seeded payments
