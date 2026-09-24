# EduPay — Backend (Package A)

FastAPI + SQLAlchemy + Alembic + Postgres. See `docs/` for the full design.

## Local dev (sandbox, no docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Point at a temp SQLite db for local sanity:
export DATABASE_URL=sqlite:///./edupay.db

# Apply migration + seed:
alembic upgrade head
python -m app.db.seed

# Run server:
uvicorn app.main:app --reload --port 8000

# Run tests (uses a temp SQLite db automatically):
pytest -q
```

## Default logins (seeded)

| Email | Password | Role |
|---|---|---|
| `admin@edupay.college` | `Password123!` | ADMIN |
| `manager@edupay.college` | `Password123!` | FINANCE_MANAGER |
| `staff@edupay.college` | `Password123!` | FINANCE_STAFF |
| `student@edupay.college` | `Password123!` | STUDENT |

300 student accounts `stu20240001@edupay.college` … `stu20240300@edupay.college` (same password).

## Layout

```
app/
  main.py            # FastAPI app + middleware + exception handlers
  core/              # config, security (JWT/hash), logging (request_id+user_id), audit
  db/                # base, session, seed
  models/            # all SQLAlchemy models
  schemas/           # pydantic schemas
  services/          # auth, user, integrity
  api/deps.py        # RBAC + request_id dependencies (auth lives here)
  api/v1/            # health, auth, users, catalog, students, admin
  tests/             # conftest, test_auth, test_models, test_integrity
alembic/versions/0001_initial.py  # hand-authored migration with every constraint
docs/                # SPEC, DECISIONS, DATA_MODEL, API (source of truth)
```

## Key invariants enforced here

- Money = `Numeric(12,2)` (Decimal). No floats.
- Financial records immutable after `SUCCESS` — reversals are linked records.
- Idempotency via DB `UNIQUE` on `payments.gateway_ref`, `payments.idempotency_key`, `idempotency_keys.key`.
- Audit row on every state transition.
- Outstanding balance is **derived** (`invoices − concessions − allocations`), never stored mutable.
- RBAC in `app.api.deps` (backend), not the frontend.
- Integrity checker `GET /admin/integrity-check` recomputes everything and reports drift.
