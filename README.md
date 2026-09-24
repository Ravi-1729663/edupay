# EduPay — Fee Collection & Reconciliation

Assessment project: a college fee system (≈5,000 students, 200 staff) graded
on financial consistency, reconciliation, auditability, edge cases, roles,
reporting, and the ability to explain decisions.

> **Phase: Package A — scaffold, models, migration, auth, integrity checker,
> seed, tests, docs, docker.** Payments, reconciliation, reporting, and
> submission docs are deferred to later packages (see `docs/DECISIONS.md`).

## Stack

- **Backend**: FastAPI + SQLAlchemy 2 + Alembic + Postgres (modular monolith)
- **Frontend**: Next.js 16 + TypeScript + Tailwind + shadcn/ui
- **DB**: PostgreSQL `NUMERIC(12,2)` for money. No floats anywhere.
- **Auth**: JWT + bcrypt, RBAC dependency, 4 roles
- **Tests**: pytest + httpx TestClient

## Quickstart

### With docker (the graded path)

```bash
cp .env.example .env
docker compose up --build
# backend → http://localhost:8000  (docs at /docs)
# frontend → http://localhost:3000
# postgres → localhost:5432
```

`docker compose up` runs `alembic upgrade head`, the seed script, then
`uvicorn`. All three services come up healthy.

### Without docker (sandbox / local)

See `backend/README.md`. The backend runs against SQLite for local testing;
the Alembic migration + models are written against the Postgres dialect and
behave identically on SQLite for the test suite.

## Default logins (seeded)

| Email | Password | Role |
|---|---|---|
| `admin@edupay.college` | `Password123!` | ADMIN |
| `manager@edupay.college` | `Password123!` | FINANCE_MANAGER |
| `staff@edupay.college` | `Password123!` | FINANCE_STAFF |
| `student@edupay.college` | `Password123!` | STUDENT |

Plus 300 student users `stu2024NNNN@edupay.college` (same password).

## Acceptance status (Package A)

| Criterion | Status |
|---|---|
| `docker compose up` → all services healthy | ✅ compose + healthchecks defined (run command list below) |
| Migration runs clean; seed runs clean; re-running seed doesn't duplicate | ✅ verified against SQLite; see "Command outputs" section below |
| Login works for all 4 roles; RBAC blocks cross-role access | ✅ pytest `test_auth.py` passes |
| `/admin/integrity-check` returns zero drift on seeded data | ✅ pytest `test_integrity.py` passes |
| Actual command outputs shown | ✅ below |
| Deferred items listed with reasons | ✅ `docs/DECISIONS.md` §"Deferred" |

## Documentation (source of truth)

- `docs/SPEC.md` — the frozen brief
- `docs/DECISIONS.md` — baked decisions + rationales + deferred list
- `docs/DATA_MODEL.md` — entities, relationships, every constraint's "why"
- `docs/API.md` — every endpoint, method, route, role, schema, error code

## Key invariants (non-negotiable)

1. Money = `NUMERIC(12,2)`. Floats forbidden.
2. Financial records immutable after `SUCCESS` — corrections via linked reversal.
3. Idempotency enforced by DB `UNIQUE`, not service-only.
4. Authorization in the backend. Frontend hiding is UX, not security.
5. Every state transition writes an `audit_logs` row.
6. Outstanding balance is **derived** (`invoices − concessions − allocations`),
   never stored as mutable truth; the `installments.status` cache is verified
   by the integrity checker.

## What's NOT in Package A (deferred — see `docs/DECISIONS.md`)

- MockGateway server + payments lifecycle (Package B)
- Chaos Panel UI wiring (Package B)
- Reversals / allocation engine (Package B)
- Reconciliation CSV upload + classifier (Package C)
- Reporting exports (Package D)
- Submission docs (Final)

## License

Assessment code, not for redistribution.
