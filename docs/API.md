# API.md — EduPay

> Source of truth for the HTTP API. Package A implements the subset marked
> **[A]**; later packages implement the rest. Every protected route lists the
> allowed roles; the backend enforces them via `deps.require_role(...)`.

**Base URL**: `/` (no version prefix in path; versioning is by Accept header +
`X-API-Version` — but for simplicity in this assessment all routes are under
`/`). All routes except `/health`, `/ready`, `/auth/login`, and
`/payments/webhook` require a `Authorization: Bearer <jwt>` header.

**Money**: every money field is a JSON string of the form `"12345.67"` to
preserve precision (never a JSON number). Pydantic `condecimal` enforces.

**Error envelope** (uniform):
```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {} // optional
  },
  "request_id": "uuid"
}
```
HTTP status codes: `400` bad request, `401` unauthenticated, `403` forbidden,
`404` not found, `409` conflict (e.g. idempotency violation), `422` validation,
`500` server error.

---

## Health & readiness

### `GET /health` — **[A]** — public
Liveness probe. Returns `200 {"status":"ok"}` unconditionally.

### `GET /ready` — **[A]** — public
Readiness probe. Checks DB connectivity. Returns
`200 {"status":"ready","db":"ok"}` or `503 {"status":"not_ready","db":"down"}`.

---

## Auth — **[A]**

### `POST /auth/login` — public
Request:
```json
{ "email": "string", "password": "string" }
```
Response `200`:
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": { "id":"uuid","email":"string","full_name":"string","role":"STUDENT" }
}
```
Errors: `401 invalid_credentials`, `422 validation`.

### `POST /auth/refresh` — any authenticated
Request: `{ "refresh_token": "string" }` (refresh tokens issued in Package B;
for Package A the access token is the only token and refresh is a no-op stub
documented here). Response `200` same as login. Errors: `401 invalid_token`.

### `GET /auth/me` — any authenticated
Response `200`: the user object above. Errors: `401`.

---

## Users — admin only — **[A]**

### `GET /users` — ADMIN
Query: `?role=&is_active=&q=&limit=50&offset=0`.
Response `200`: `{ "items":[User], "total":int, "limit":int, "offset":int }`.

### `POST /users` — ADMIN
Request:
```json
{ "email":"string","password":"string","full_name":"string",
  "role":"STUDENT|FINANCE_STAFF|FINANCE_MANAGER|ADMIN",
  "student_id":"uuid|null" }
```
Response `201`: User (no password_hash). Errors: `409 email_exists`, `422`,
`403` (non-admin).

### `GET /users/{id}` — ADMIN
Response `200`: User. Errors: `404`.

### `PATCH /users/{id}` — ADMIN
Request: any subset of `{ "full_name","role","is_active","student_id" }`.
Response `200`: User. Errors: `404`,`409`,`422`.

### `POST /users/{id}/deactivate` — ADMIN
Soft-deactivate (`is_active=false`). Response `200`: User.

---

## Departments / Programs / Fee catalog — **[A]** (read), [B/C] (write)

### `GET /departments` — any authenticated
Response `200`: `{ "items":[{ "id","code","name" }] }`.

### `GET /programs` — any authenticated
Query: `?department_id=`. Response `200`: list of programs.

### `GET /fee-heads` — any authenticated
Response `200`: list of fee heads with `priority`.

### `GET /fee-structures` — FINANCE_STAFF, FINANCE_MANAGER, ADMIN
Query: `?program_id=&academic_year=&is_active=`. Response `200`: list with
nested `lines`.

### `POST /fee-structures` — FINANCE_MANAGER, ADMIN — **[B]**
Request: `{ "program_id","academic_year","effective_from","effective_to","lines":[{ "fee_head_id","amount" }] }`.
Response `201`: the structure. Errors: `409 duplicate_program_year`.

### `POST /student-fee-assignments` — FINANCE_STAFF, FINANCE_MANAGER — **[B]**
Request: `{ "student_id","fee_structure_id","academic_year","installments":[{ "due_date","amount","fee_head_id|null" }] }`.
Response `201`: the assignment + installments. Errors: `409 already_assigned`,
`422 amounts_must_sum_to_structure_total`.

---

## Students — **[A]** (read for own data + staff)

### `GET /students` — FINANCE_STAFF, FINANCE_MANAGER, ADMIN
Query: `?q=&program_id=&batch_year=&status=&limit=50&offset=0`.
Response `200`: paginated list.

### `GET /students/{id}` — STUDENT (self only) + staff/manager/admin
Response `200`: student detail. Errors: `403` (other student), `404`.

### `GET /students/{id}/outstanding` — STUDENT (self) + staff/manager/admin — **[A]**
Returns the **derived** outstanding: `invoiced − concessions − allocations`,
broken down by installment and fee head.
Response `200`:
```json
{
  "student_id":"uuid",
  "total_invoiced":"120000.00",
  "total_concessions":"0.00",
  "total_allocated":"0.00",
  "total_outstanding":"120000.00",
  "by_installment":[{"installment_id","due_date","amount","outstanding","status"}]
}
```

### `GET /students/{id}/installments` — STUDENT (self) + staff — **[A]**
Response `200`: list of installments with derived outstanding.

### `GET /students/{id}/payments` — STUDENT (self) + staff — **[B]**

---

## Concessions — **[B]** (Package A seeds 2 pending)

### `GET /concessions` — FINANCE_STAFF, FINANCE_MANAGER, ADMIN
Query: `?student_id=&status=`.

### `POST /concessions` — FINANCE_STAFF, FINANCE_MANAGER
Request: `{ "student_id","fee_head_id|null","installment_id|null","amount","reason" }`.
Response `201`.

### `POST /concessions/{id}/approve` — FINANCE_MANAGER, ADMIN
Response `200`: concession with `status=APPROVED`. Errors: `409 already_decided`.

### `POST /concessions/{id}/reject` — FINANCE_MANAGER, ADMIN
Response `200`: concession with `status=REJECTED`.

---

## Payments — **[B]** (Package A: schema + tables only)

### `POST /payments/counter` — FINANCE_STAFF, FINANCE_MANAGER
Staff counter collection (cash/cheque) → recorded as `SUCCESS` directly.
Request:
```json
{
  "student_id":"uuid",
  "amount":"10000.00",
  "method":"CASH|CHEQUE",
  "cheque_number":"string|null",
  "idempotency_key":"string",
  "allocate_to":[ {"installment_id","fee_head_id","amount"} ] // optional, can be left to auto-allocation
}
```
Response `201`: payment with `status=SUCCESS` + allocations. Errors:
`409 idempotency_conflict`, `422 amount_le_outstanding`, `422 method_online_requires_gateway`.

### `POST /payments/initiate` — STUDENT (self), FINANCE_STAFF
Student self-service via MockGateway → full async lifecycle.
Request:
```json
{
  "student_id":"uuid",
  "amount":"10000.00",
  "method":"ONLINE",
  "idempotency_key":"string",
  "return_url":"string"
}
```
Response `202`: `{ "payment_id","status":"PENDING","gateway_ref","gateway_redirect_url" }`.
Errors: `409 idempotency_conflict`.

### `GET /payments/{id}` — STUDENT (self), FINANCE_STAFF, FINANCE_MANAGER, ADMIN
Response `200`: payment + allocations + reversal (if any).

### `GET /payments` — FINANCE_STAFF, FINANCE_MANAGER, ADMIN
Query: `?student_id=&status=&from=&to=`.

### `POST /payments/{id}/verify` — FINANCE_STAFF, FINANCE_MANAGER
Resolve `UNKNOWN` by polling the gateway. Response `200`: updated payment.

### `POST /payments/{id}/reversal-request` — FINANCE_MANAGER, ADMIN
Request: `{ "amount","reason" }`. Response `201`: reversal record `REQUESTED`.
Errors: `409 not_in_success_state`, `422 amount_le_original`.

### `POST /payments/{id}/reversal-complete` — FINANCE_MANAGER, ADMIN
Response `200`: reversal `COMPLETED`, original payment `REVERSED`. Errors:
`409 already_completed`.

### `POST /payments/{id}/allocate` — FINANCE_STAFF, FINANCE_MANAGER
Apply an unallocated `SUCCESS` payment to installments (oldest-due first).
Response `200`: allocations.

### `GET /payments/{id}/allocations` — STUDENT (self), staff
Response `200`: list.

### `POST /payments/webhook` — public (signed; `X-Gateway-Signature`)
Gateway async callback. Body: `{ "gateway_ref","status","amount","paid_at" }`.
Idempotent on `gateway_ref`. Response `200` always (so gateway doesn't retry-penalise).

---

## Reconciliation — **[C]**

### `POST /reconciliation/upload` — FINANCE_MANAGER, ADMIN
`multipart/form-data` with a CSV: `external_reference,external_amount,student_roll_number?`.
Response `201`: batch summary with classification counts.

### `GET /reconciliation/batches` — FINANCE_MANAGER, ADMIN
### `GET /reconciliation/batches/{id}` — FINANCE_MANAGER, ADMIN
### `GET /reconciliation/batches/{id}/lines` — FINANCE_MANAGER, ADMIN
Query: `?classification=`.
### `POST /reconciliation/lines/{id}/resolve` — FINANCE_MANAGER, ADMIN
Manually pin a line to a payment/student (with audit row).

---

## Admin — **[A]**

### `GET /admin/integrity-check` — FINANCE_MANAGER, ADMIN
Response `200`:
```json
{
  "ok": true,
  "checked_at":"2024-01-01T00:00:00Z",
  "students_checked": 300,
  "installments_checked": 900,
  "payments_checked": 0,
  "drifts": [],
  "invariant_violations": []
}
```
On drift, `ok=false` and `drifts` lists per-installment drifts, and
`invariant_violations` lists any cross-row invariant breach
(allocation > payment, reversal > original, impossible state). This endpoint
must return zero drift on freshly seeded data — asserted in pytest.

### `GET /admin/audit-logs` — FINANCE_MANAGER, ADMIN
Query: `?entity_type=&entity_id=&actor_user_id=&from=&to=&limit=100&offset=0`.
Response `200`: paginated audit rows.

---

## Mock Gateway — **[B]**

### `POST /mock-gateway/pay` — internal (called by `payments/initiate`)
Request: `{ "payment_id","amount","student_id","idempotency_key","chaos" }`.
Response `202`: `{ "gateway_ref","redirect_url","status":"PENDING" }`. Then
async callback to `/payments/webhook` per the chaos setting.

### `GET /mock-gateway/chaos` — ADMIN (dev)
Returns the current chaos setting.

### `POST /mock-gateway/chaos` — ADMIN (dev)
Body: `{ "mode":"SUCCESS|FAILED|TIMEOUT_NO_CALLBACK|DUPLICATE_CALLBACK|LATE_CALLBACK","delay_seconds":0 }`.
Stores the setting for the *next* payment. Used by the Chaos Panel.

---

## Reporting — **[D]**

### `GET /reports/collected-summary` — FINANCE_MANAGER, ADMIN
### `GET /reports/outstanding-summary` — FINANCE_MANAGER, ADMIN
### `GET /reports/overdue-summary` — FINANCE_MANAGER, ADMIN
### `GET /reports/concessions-summary` — FINANCE_MANAGER, ADMIN
### `GET /reports/reconciliation-summary/{batch_id}` — FINANCE_MANAGER, ADMIN

All return CSS-bar-friendly flat JSON.

---

## Package A endpoints actually implemented this session

| Method | Route | Status |
|---|---|---|
| GET | `/health` | ✅ |
| GET | `/ready` | ✅ |
| POST | `/auth/login` | ✅ |
| GET | `/auth/me` | ✅ |
| GET | `/users` | ✅ |
| POST | `/users` | ✅ |
| GET | `/users/{id}` | ✅ |
| PATCH | `/users/{id}` | ✅ |
| POST | `/users/{id}/deactivate` | ✅ |
| GET | `/departments` | ✅ |
| GET | `/programs` | ✅ |
| GET | `/fee-heads` | ✅ |
| GET | `/fee-structures` | ✅ |
| GET | `/students` | ✅ |
| GET | `/students/{id}` | ✅ |
| GET | `/students/{id}/outstanding` | ✅ |
| GET | `/students/{id}/installments` | ✅ |
| GET | `/admin/integrity-check` | ✅ |
| GET | `/admin/audit-logs` | ✅ |

All other routes in this document are documented for later packages and
return `501 Not Implemented` if hit during Package A.
