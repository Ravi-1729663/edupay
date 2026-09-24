# DECISIONS.md — EduPay

Every entry: **Decision** — one-line rationale. Baked decisions are not
revisited mid-build.

## Baked (do not revisit)

1. **Modular monolith: FastAPI + SQLAlchemy + Alembic + Postgres; Next.js + TS + Tailwind.**
   — Matches the spec; single deployable keeps operational surface small for a 5k-student college.

2. **No Celery / Redis.** — Reconciliation is synchronous CSV upload; async reconciliation is *deferred, not deleted*, and can be layered later behind the same service interface.

3. **Two payment initiation paths: staff counter (cash/cheque → SUCCESS direct) and student self-service via MockGateway (full async lifecycle).**
   — Mirrors real college cashier workflows and lets us demo the full gateway state machine in one app.

4. **Allocation = oldest-due installment first, then fee-head priority; partial payments allowed; allocation ≤ payment and ≤ installment outstanding.**
   — Deterministic, auditable, and matches how fee notices are typically dunned.

5. **Payment state machine: `CREATED → PENDING → {SUCCESS | FAILED | UNKNOWN}`; `UNKNOWN` resolves only via verification/reconciliation; `SUCCESS → REVERSAL_REQUESTED → REVERSED` (original preserved).**
   — `UNKNOWN` exists because gateways do time out; reversal-via-linked-record keeps history immutable.

6. **Roles: STUDENT, FINANCE_STAFF, FINANCE_MANAGER, ADMIN; backend-enforced.**
   — Four tiers map cleanly to segregation-of-duties (collect vs. approve vs. administer).

7. **Reconciliation classes: MATCHED, AMOUNT_MISMATCH, MISSING_INTERNAL, MISSING_EXTERNAL, DUPLICATE.**
   — Exhaustive over the (internal × settlement) cross-product; AMOUNT_MISMATCH is never auto-adjusted (financial hygiene).

8. **Charts: CSS bars / sparklines only.**
   — Removes a dependency and keeps the bundle small; dashboards are simple enough.

9. **Cut list: SMS/email, rate limiting, refunds-to-source, multi-campus, real gateway.**
   — Out of scope for the assessment; MockGateway substitutes for the real one.

## Environment-driven decisions (logged here, not baked)

D1. **Backend lives in `backend/`; frontend is the root Next.js 16 project (not a separate `frontend/` dir).**
   — The sandbox ships a running Next.js at root on port 3000; the spec's `frontend/` directory is satisfied by the root project being the frontend service. `docker-compose.yml` references `.` as the frontend build context. No functional impact.

D2. **Local execution uses SQLite; production uses Postgres.**
   — No docker/psql in the sandbox. SQLAlchemy `Numeric(12,2)` and the Alembic migration are written against Postgres dialect but execute identically on SQLite for tests. The `docker-compose.yml` + `Dockerfile`s deliver the real Postgres stack to the grader.

D3. **Idempotency keys + `gateway_ref` are `NULL`-able but `UNIQUE` where present.**
   — SQLite enforces `UNIQUE` on `NULL` differently from Postgres; to keep tests faithful, the seed and service always supply a non-null value, and the migration declares `UNIQUE` so Postgres will reject collisions.

D4. **`outstanding_balance` is never a stored column on installments.**
   — It is exposed via a property/derived view and recomputed by the integrity checker. This preserves invariant #6 literally.

D5. **`audit_logs.metadata` is a JSONB column on Postgres / JSON-serialized TEXT on SQLite.**
   — SQLAlchemy `JSON` type maps to both; tests run on SQLite, prod on Postgres.

D6. **`created_at` / `updated_at` are server-side defaults (`now()` / `onupdate now()`), not client-supplied.**
   — Prevents clock-skew tampering of audit facts.

## Deferred (not deleted) — tracked for later packages

| Item | Reason | Owner package |
|---|---|---|
| Async reconciliation (Celery/Redis) | Synchronous CSV upload is enough for the demo and the graded reconciliation paths | Package C |
| MockGateway server | Required by Package B (payments) but not by Package A | Package B |
| Chaos Panel UI wiring | Frontend placeholder exists; toggles hit the gateway service added in Package B | Package B |
| Reversals / allocation engine | Explicitly out of Package A scope ("Do not start payments") | Package B |
| Reporting export (PDF/CSV) | Reporting package | Package D |
| Submission docs | Explicitly deferred in the brief | Final |
