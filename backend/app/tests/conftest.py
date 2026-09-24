"""Pytest fixtures.

We run tests against a fresh SQLite DB (in-memory or temp file) pointed at by
`DATABASE_URL` before the app is imported. The schema is created via the
Alembic migration (so the migration is exercised by tests), then the seed
script is run so tests have realistic data.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Force a temp SQLite DB BEFORE importing `app` (config caches the URL).
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP.name}"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["JWT_EXPIRE_MINUTES"] = "60"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"

# Ensure backend/ is on sys.path so `import app` works.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine, get_db  # noqa: E402
import app.models  # noqa: E402,F401  register all tables


@pytest.fixture(scope="session")
def db_setup():
    """Run the migration + seed once per session."""
    # Use Alembic to create the schema (exercises the migration).
    cfg = Config(str(Path(__file__).resolve().parent.parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{_TMP.name}")
    command.upgrade(cfg, "head")
    # Seed.
    from app.db.seed import run as seed_run
    seed_run(reset=False)
    yield
    import os as _os
    try:
        _os.unlink(_TMP.name)
    except OSError:
        pass


@pytest.fixture()
def db(db_setup):
    """Per-test session; rolled back after each test."""
    connection = engine.connect()
    trans = connection.begin()
    session = SessionLocal(bind=connection)
    yield session
    session.close()
    trans.rollback()
    connection.close()


@pytest.fixture()
def client(db_setup):
    """FastAPI test client with a per-test DB session override."""
    connection = engine.connect()
    trans = connection.begin()
    session = SessionLocal(bind=connection)

    def _override():
        try:
            yield session
        finally:
            pass

    from app.main import app
    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session.close()
    trans.rollback()
    connection.close()


# ── Login helpers ───────────────────────────────────────────────────
CREDENTIALS = {
    "ADMIN": ("admin@edupay.college", "Password123!"),
    "FINANCE_MANAGER": ("manager@edupay.college", "Password123!"),
    "FINANCE_STAFF": ("staff@edupay.college", "Password123!"),
    "STUDENT": ("student@edupay.college", "Password123!"),
}


def login(client, role: str) -> str:
    email, pw = CREDENTIALS[role]
    r = client.post("/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
