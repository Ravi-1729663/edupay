"""Integrity checker tests — must return zero drift on freshly seeded data."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.integrity_service import check as integrity_check
from app.tests.conftest import auth_header, login


def test_integrity_zero_drift_on_seeded_data(db) -> None:
    report = integrity_check(db)
    assert report.ok is True, f"expected zero drift, got {len(report.drifts)} drifts and {len(report.invariant_violations)} violations"
    assert report.drifts == []
    assert report.invariant_violations == []
    assert report.students_checked == 300
    # 300 students × 3 installments = 900 installments (plus the demo student
    # which is not in the seeded-300 set but may have an assignment).
    assert report.installments_checked >= 900


def test_integrity_via_endpoint_requires_manager(client: TestClient) -> None:
    mgr = login(client, "FINANCE_MANAGER")
    r = client.get("/admin/integrity-check", headers=auth_header(mgr))
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["drifts"] == []
    assert body["invariant_violations"] == []
    assert body["students_checked"] == 300


def test_integrity_via_endpoint_admin(client: TestClient) -> None:
    admin = login(client, "ADMIN")
    r = client.get("/admin/integrity-check", headers=auth_header(admin))
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_integrity_detects_drift_when_status_cache_corrupted(db) -> None:
    """Tamper the installments.status cache and confirm the checker reports drift."""
    from sqlalchemy import select, update
    from app.models.fee import Installment, InstallmentStatus
    # Pick a PENDING or OVERDUE installment and flip its cached status to PAID.
    inst = db.execute(
        select(Installment).where(Installment.status != InstallmentStatus.PAID).limit(1)
    ).scalar_one()
    db.execute(
        update(Installment).where(Installment.id == inst.id).values(status=InstallmentStatus.PAID)
    )
    db.flush()
    report = integrity_check(db)
    assert report.ok is False
    assert any(d.installment_id == inst.id for d in report.drifts), "drift must be reported on the tampered installment"
