"""Auth tests: valid login, invalid login, role restrictions, /me."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.tests.conftest import CREDENTIALS, auth_header, login


def test_login_admin_success(client: TestClient) -> None:
    token = login(client, "ADMIN")
    assert token and isinstance(token, str)
    r = client.get("/auth/me", headers=auth_header(token))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "admin@edupay.college"
    assert body["role"] == "ADMIN"


def test_login_all_roles(client: TestClient) -> None:
    for role in ["ADMIN", "FINANCE_MANAGER", "FINANCE_STAFF", "STUDENT"]:
        token = login(client, role)
        assert token, f"{role} should log in"


def test_login_wrong_password(client: TestClient) -> None:
    email, _ = CREDENTIALS["ADMIN"]
    r = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "invalid_credentials"
    assert "request_id" in body


def test_login_unknown_email(client: TestClient) -> None:
    r = client.post("/auth/login", json={"email": "nobody@nowhere.dev", "password": "whatever"})
    assert r.status_code == 401


def test_me_without_token(client: TestClient) -> None:
    r = client.get("/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


def test_me_with_bad_token(client: TestClient) -> None:
    r = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_rbac_admin_only_route_blocks_student(client: TestClient) -> None:
    # /users (list) is ADMIN-only.
    student_token = login(client, "STUDENT")
    r = client.get("/users", headers=auth_header(student_token))
    assert r.status_code == 403
    body = r.json()
    assert body["error"]["code"] == "forbidden"


def test_rbac_admin_only_route_allows_admin(client: TestClient) -> None:
    admin_token = login(client, "ADMIN")
    r = client.get("/users", headers=auth_header(admin_token))
    assert r.status_code == 200


def test_rbac_integrity_check_blocks_staff(client: TestClient) -> None:
    # /admin/integrity-check is FINANCE_MANAGER + ADMIN only.
    staff_token = login(client, "FINANCE_STAFF")
    r = client.get("/admin/integrity-check", headers=auth_header(staff_token))
    assert r.status_code == 403


def test_rbac_integrity_check_allows_manager(client: TestClient) -> None:
    mgr_token = login(client, "FINANCE_MANAGER")
    r = client.get("/admin/integrity-check", headers=auth_header(mgr_token))
    assert r.status_code == 200


def test_rbac_student_cannot_list_students(client: TestClient) -> None:
    token = login(client, "STUDENT")
    r = client.get("/students", headers=auth_header(token))
    assert r.status_code == 403


def test_rbac_student_cannot_see_other_student_detail(client: TestClient) -> None:
    # student@edupay.college is the demo student; the seeded roll STU20240001 is
    # a different student. The STUDENT user can only fetch their own id.
    from app.db.session import SessionLocal
    from app.models.student import Student
    from sqlalchemy import select

    db = SessionLocal()
    try:
        other = db.execute(select(Student).where(Student.roll_number == "STU20240001")).scalar_one()
        other_id = other.id
    finally:
        db.close()
    token = login(client, "STUDENT")
    r = client.get(f"/students/{other_id}/outstanding", headers=auth_header(token))
    assert r.status_code == 403
