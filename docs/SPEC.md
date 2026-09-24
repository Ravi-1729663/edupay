# EduPay — Fee Collection & Reconciliation System (SPEC)

> Status: Frozen for Package A. This document mirrors the graded brief.
> Any deviation is recorded in `docs/DECISIONS.md` with a one-line rationale.

## 1. Overview
A fee collection & reconciliation system ("EduPay") for a college of ~5,000
students and 200 staff. Graded on: **financial consistency, reconciliation,
auditability, edge cases, role-based access, reporting, and the ability to
explain design decisions.**

## 2. Non-Negotiable Invariants
1. **Money = PostgreSQL `NUMERIC(12,2)`. Floats are forbidden.** All money
   columns use SQLAlchemy `Numeric(12, 2)`; Python `decimal.Decimal` everywhere
   in the service layer.
2. **Financial records are IMMUTABLE.** Corrections happen via linked reversal
   entries; nothing is `UPDATE`d or `DELETE`d after a record reaches `SUCCESS`.
3. **Idempotency is enforced by a database `UNIQUE` constraint**, never by a
   service-layer check alone.
4. **Authorization lives in the backend.** Frontend hiding is UX, not security.
5. **Every state transition writes an `audit_logs` row** with
   `(actor, action, entity, entity_id, ts, metadata)`.
6. **Outstanding balance is always DERIVED**:
   `outstanding = invoiced − concessions − allocations`. It is never stored as
   mutable truth. (Cached read-models may exist but must be recomputable from
   base facts and validated by the integrity checker.)

## 3. Baked Decisions (do not revisit)
1. **Modular monolith.** FastAPI + SQLAlchemy + Alembic + Postgres for the
   backend; Next.js + TypeScript + Tailwind for the frontend.
2. **No Celery / Redis.** Reconciliation is a synchronous CSV upload. (Async
   processing is *deferred, not deleted* — see DECISIONS.md.)
3. **Payment initiation supports both:**
   - **(a) Staff counter collection** (cash/cheque) → recorded as `SUCCESS`
     directly (no gateway round-trip).
   - **(b) Student self-service via MockGateway** → full async lifecycle.
4. **Allocation strategy:** oldest-due installment first, then fee-head
   priority. Partial payments allowed. Allocation can never exceed the payment
   amount or the installment outstanding.
5. **Payment state machine:**
   ```
   CREATED → PENDING → {SUCCESS | FAILED | UNKNOWN}
   UNKNOWN → resolves only via verification / reconciliation.
   SUCCESS → REVERSAL_REQUESTED → REVERSED  (original record preserved)
   ```
6. **Roles:** `STUDENT`, `FINANCE_STAFF`, `FINANCE_MANAGER`, `ADMIN`.
   Backend-enforced via FastAPI dependency.
7. **Reconciliation classifications:**
   | Class | Definition |
   |---|---|
   | `MATCHED` | same reference + same amount |
   | `AMOUNT_MISMATCH` | reference matches, amount differs — flag, never auto-adjust |
   | `MISSING_INTERNAL` | settlement line exists, no internal payment |
   | `MISSING_EXTERNAL` | internal `SUCCESS` payment, no settlement line |
   | `DUPLICATE` | same external reference settling twice |
8. **Charts:** simple CSS bars / sparklines only. No chart library.
9. **Cut list (do not build):** SMS/email, rate limiting, refunds-to-source,
   multi-campus, real gateway integration.

## 4. Mock Gateway Spec (critical — the demo depends on it)
- `POST /mock-gateway/pay` → returns a gateway reference, then performs an
  async callback to the backend webhook.
- **Chaos mode** setting forces the next outcome to one of:
  `SUCCESS | FAILED | TIMEOUT_NO_CALLBACK | DUPLICATE_CALLBACK (fire 2) |
  LATE_CALLBACK (delay N seconds)`.
- A **dev-only Chaos Panel** page in the frontend toggles this. Every failure
  scenario must be demoable live through the UI, not just in tests.

## 5. Integrity Checker (differentiator)
`GET /admin/integrity-check` (roles: `FINANCE_MANAGER`, `ADMIN`):
- Recompute every student's outstanding from base facts
  `(invoices − concessions − allocations)` and report any drift vs. computed
  installment status.
- Verify:
  - no allocation exceeds its payment;
  - no reversal exceeds its original;
  - no `SUCCESS` payment is in an impossible state.
- Return a zero-drift report. Also expressed as a pytest on seeded data.

## 6. Package A Scope (this session — nothing more)
1. Repo scaffold (backend modules, frontend, docker-compose, Dockerfiles,
   `.env.example`, `.gitignore`, README skeleton).
2. **All** SQLAlchemy models + one Alembic migration, with real constraints.
3. `docs/DATA_MODEL.md` and `docs/API.md` — the source of truth for later
   packages; must be complete.
4. `docs/DECISIONS.md` initialized with the baked decisions + one-line
   rationale each.
5. Auth: JWT, password hashing, RBAC FastAPI dependency, 4 roles, user CRUD
   (admin only).
6. `GET /health`, `GET /ready`. Structured logging with `request_id` + `user_id`.
7. Seed script v1 (re-runnable): departments, programs, ~300 students, 6 fee
   heads, fee structures, student fee assignments, installments with due dates
   spread across past/current/future, 2 concession requests pending approval.
8. Pytest: auth (valid/invalid/role restrictions), model constraint tests.

## 7. Package A Acceptance
- [ ] `docker compose up` → all services healthy
- [ ] Migration runs clean; seed runs clean; re-running seed doesn't duplicate
- [ ] Login works for all 4 roles; RBAC blocks cross-role access (tested)
- [ ] `/admin/integrity-check` returns zero drift on seeded data
- [ ] Actual command outputs shown; deferred items listed with reasons

**Then STOP and wait. Do not start payments. Do not start submission docs.**
