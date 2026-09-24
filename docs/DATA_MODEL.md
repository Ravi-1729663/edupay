# DATA_MODEL.md — EduPay

> Source of truth for the database schema. The Alembic migration in
> `backend/alembic/versions/0001_initial.py` is generated from this document.
> Money is **always** `Numeric(12, 2)` (Postgres `NUMERIC(12,2)`,
> Python `decimal.Decimal`). Floats are forbidden.

## Conventions

- **Primary keys**: UUID (stored as `VARCHAR(36)` / Postgres `UUID` depending on
  dialect) for all domain entities, except `audit_logs` which uses a bigserial
  `id` because it is append-only and high-volume.
- **Money type**: `Numeric(12, 2)` everywhere. `Decimal` in Python. No
  `Float`/`REAL` columns exist in the schema.
- **Timestamps**: `created_at` (server default `now()`) and `updated_at`
  (`onupdate now()`) on every financial table. `created_by` (FK → `users.id`)
  on every financial table for auditability.
- **Soft deletes**: forbidden on financial records. Reversals handle corrections.
- **Immutability**: a `payment`, `payment_allocation`, or `concession` that
  reaches a terminal state (`SUCCESS`, `APPROVED`, `REVERSED`) is never
  `UPDATE`d again except to transition to a linked-state (`REVERSAL_REQUESTED`,
  `REVERSED`). The original row is preserved; `audit_logs` records the
  transition.
- **Derived balances**: `outstanding_balance` is **never a stored column**.
  It is computed in queries / views and recomputed by the integrity checker.
  The `installments.status` column is a *cache* that must equal the derived
  value; the integrity checker reports drift if it does not.
- **Idempotency** is enforced by DB `UNIQUE` constraints on
  `payments.gateway_ref`, `payments.idempotency_key`, and a dedicated
  `idempotency_keys` table. Service-layer checks are advisory only.

## Entities

### 1. `users`
Authentication + RBAC.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `email` | VARCHAR(255) | UNIQUE NOT NULL | login identifier |
| `password_hash` | VARCHAR(255) | NOT NULL | bcrypt |
| `full_name` | VARCHAR(255) | NOT NULL | |
| `role` | VARCHAR(32) | NOT NULL CHECK in (STUDENT, FINANCE_STAFF, FINANCE_MANAGER, ADMIN) | |
| `is_active` | BOOL | NOT NULL DEFAULT true | |
| `student_id` | UUID FK→students.id | NULL | set only for STUDENT role |
| `created_at` | TIMESTAMP | NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMP | NOT NULL DEFAULT now() | |
| `created_by` | UUID FK→users.id | NULL | |

Indexes: unique on `email`; index on `role`.

### 2. `departments`
College academic departments.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `code` | VARCHAR(32) | UNIQUE NOT NULL |
| `name` | VARCHAR(255) | NOT NULL |
| `created_at`/`updated_at` | TIMESTAMP | defaults |

### 3. `programs`
Degree programs offered by a department.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `code` | VARCHAR(32) | UNIQUE NOT NULL |
| `name` | VARCHAR(255) | NOT NULL |
| `department_id` | UUID FK→departments.id | NOT NULL |
| `duration_years` | SMALLINT | NOT NULL CHECK > 0 |
| `created_at`/`updated_at` | TIMESTAMP | defaults |

### 4. `students`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `roll_number` | VARCHAR(32) | UNIQUE NOT NULL | |
| `full_name` | VARCHAR(255) | NOT NULL | |
| `email` | VARCHAR(255) | NOT NULL | not unique (could share family email) |
| `phone` | VARCHAR(20) | NULL | |
| `program_id` | UUID FK→programs.id | NOT NULL | |
| `batch_year` | SMALLINT | NOT NULL | e.g. 2023 |
| `status` | VARCHAR(16) | NOT NULL CHECK in (ACTIVE, GRADUATED, WITHDRAWN) | |
| `created_at`/`updated_at`/`created_by` | TIMESTAMP/UUID | defaults |

Indexes: on `program_id`, `batch_year`, `status`.

### 5. `fee_heads`
Catalog of fee categories. Six seeded: TUITION, LAB, LIBRARY, EXAM, HOSTEL, MESS.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `code` | VARCHAR(32) | UNIQUE NOT NULL | |
| `name` | VARCHAR(255) | NOT NULL | |
| `description` | TEXT | NULL | |
| `priority` | SMALLINT | NOT NULL DEFAULT 100 | allocation tiebreak (lower = higher priority) |
| `is_refundable` | BOOL | NOT NULL DEFAULT false | |
| `created_at`/`updated_at` | TIMESTAMP | defaults |

### 6. `fee_structures`
A fee schedule for a program in an academic year.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `program_id` | UUID FK→programs.id | NOT NULL |
| `academic_year` | VARCHAR(16) | NOT NULL (e.g. "2024-2025") |
| `effective_from` | DATE | NOT NULL |
| `effective_to` | DATE | NOT NULL |
| `is_active` | BOOL | NOT NULL DEFAULT true |
| `created_at`/`updated_at`/`created_by` | defaults |

Unique: `(program_id, academic_year)`. Index on `is_active`.

### 7. `fee_structure_lines`
One row per `(fee_structure, fee_head)` — the invoiced amount for that head.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `fee_structure_id` | UUID FK→fee_structures.id | NOT NULL |
| `fee_head_id` | UUID FK→fee_heads.id | NOT NULL |
| `amount` | Numeric(12,2) | NOT NULL CHECK > 0 |
| `created_at`/`updated_at` | defaults |

Unique: `(fee_structure_id, fee_head_id)`.

### 8. `student_fee_assignments`
Snapshot of a fee structure applied to a student for an academic year.
`total_invoiced` is a snapshot of `Σ lines.amount` at assignment time
(immutable; if the structure changes later, a new assignment or a new
installment is created — never edited).

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `student_id` | UUID FK→students.id | NOT NULL |
| `fee_structure_id` | UUID FK→fee_structures.id | NOT NULL |
| `academic_year` | VARCHAR(16) | NOT NULL |
| `total_invoiced` | Numeric(12,2) | NOT NULL CHECK ≥ 0 |
| `created_at`/`updated_at`/`created_by` | defaults |

Unique: `(student_id, academic_year)`. Index on `student_id`.

### 9. `installments`
Each assignment is split into N installments with due dates. For Package A
the seed creates 3 installments per assignment spread across past/current/future.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `student_fee_assignment_id` | UUID FK→student_fee_assignments.id | NOT NULL | |
| `installment_number` | SMALLINT | NOT NULL | 1-based |
| `due_date` | DATE | NOT NULL | |
| `amount` | Numeric(12,2) | NOT NULL CHECK > 0 | invoiced amount for this installment |
| `fee_head_id` | UUID FK→fee_heads.id | NULL | NULL = composite installment covering all heads |
| `status` | VARCHAR(24) | NOT NULL DEFAULT 'PENDING' CHECK in (PENDING, PARTIALLY_PAID, PAID, OVERDUE) | **cached**; integrity checker recomputes |
| `created_at`/`updated_at`/`created_by` | defaults | | |

Unique: `(student_fee_assignment_id, installment_number)`.
Indexes: on `due_date` (overdue queries), `student_fee_assignment_id`, `status`.

> **Why a `status` cache column at all?** Pure derivation in queries is
> expensive at 5k students × 3 installments × N allocations. The cache makes
> dashboards fast; the integrity checker makes it *honest*. Drift = bug.

### 10. `concessions`
Approved/rejected concession requests. Once `APPROVED`, the row is immutable;
a linked reversal concession (future package) undoes its effect, not an edit.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `student_id` | UUID FK→students.id | NOT NULL |
| `fee_head_id` | UUID FK→fee_heads.id | NULL | NULL = applies to whole assignment |
| `installment_id` | UUID FK→installments.id | NULL | NULL = applies to all installments of that head |
| `amount` | Numeric(12,2) | NOT NULL CHECK > 0 |
| `reason` | TEXT | NOT NULL |
| `status` | VARCHAR(16) | NOT NULL DEFAULT 'PENDING' CHECK in (PENDING, APPROVED, REJECTED) |
| `approved_by` | UUID FK→users.id | NULL |
| `approved_at` | TIMESTAMP | NULL |
| `created_at`/`updated_at`/`created_by` | defaults |

Indexes: on `student_id`, `status`.

### 11. `payments`
The core financial record. Immutable after `SUCCESS` except for the
`SUCCESS → REVERSAL_REQUESTED → REVERSED` transition.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `student_id` | UUID FK→students.id | NOT NULL | |
| `payer_user_id` | UUID FK→users.id | NULL | NULL for walk-in counter collection |
| `amount` | Numeric(12,2) | NOT NULL CHECK > 0 | |
| `method` | VARCHAR(16) | NOT NULL CHECK in (CASH, CHEQUE, ONLINE) | |
| `gateway_ref` | VARCHAR(128) | **UNIQUE** NULL | required for ONLINE; NULL for CASH/CHEQUE |
| `status` | VARCHAR(24) | NOT NULL DEFAULT 'CREATED' CHECK in (CREATED, PENDING, SUCCESS, FAILED, UNKNOWN, REVERSAL_REQUESTED, REVERSED) | |
| `idempotency_key` | VARCHAR(128) | **UNIQUE** NULL | client-supplied; DB-enforced |
| `initiated_by` | UUID FK→users.id | NOT NULL | |
| `callback_received_at` | TIMESTAMP | NULL | |
| `metadata` | JSON | NULL | |
| `created_at`/`updated_at`/`created_by` | defaults | | |

**CHECK constraint**: `method = 'ONLINE' AND gateway_ref IS NULL` is forbidden
(i.e. `(method <> 'ONLINE' OR gateway_ref IS NOT NULL)`).
Indexes: unique `gateway_ref`; unique `idempotency_key`; on `student_id`, `status`, `created_at`.

### 12. `payment_allocations`
How a `SUCCESS` payment is applied to installments/fee-heads.
`allocated ≤ payment.amount` is enforced by a CHECK *cannot* reference another
row, so it is enforced (a) in the service layer, (b) via a Postgres trigger
(shipped with the migration for prod), and (c) re-verified by the integrity
checker. The trigger is included to keep the invariant a *DB* invariant, not
just a service invariant.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `payment_id` | UUID FK→payments.id | NOT NULL |
| `installment_id` | UUID FK→installments.id | NOT NULL |
| `fee_head_id` | UUID FK→fee_heads.id | NOT NULL |
| `amount` | Numeric(12,2) | NOT NULL CHECK > 0 |
| `created_at`/`updated_at`/`created_by` | defaults |

Unique: `(payment_id, installment_id, fee_head_id)`.
Indexes: on `payment_id`, `installment_id`.

### 13. `payment_reversals`
Linked reversal of a `SUCCESS` payment. Original `payments` row is preserved
(transitioned to `REVERSED`); this row records the reversal.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `original_payment_id` | UUID FK→payments.id | NOT NULL |
| `amount` | Numeric(12,2) | NOT NULL CHECK > 0 |
| `reason` | TEXT | NOT NULL |
| `status` | VARCHAR(16) | NOT NULL DEFAULT 'REQUESTED' CHECK in (REQUESTED, COMPLETED) |
| `requested_by` | UUID FK→users.id | NOT NULL |
| `completed_at` | TIMESTAMP | NULL |
| `created_at`/`updated_at`/`created_by` | defaults |

Index on `original_payment_id`. The "reversal ≤ original" invariant is
enforced in service + integrity checker (cross-row CHECK is awkward) and
documented in `docs/DATA_MODEL.md` as the source of truth.

### 14. `reconciliation_batches`
A CSV upload session.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `uploaded_by` | UUID FK→users.id | NOT NULL |
| `source_file_name` | VARCHAR(255) | NOT NULL |
| `total_lines` | INT | NOT NULL DEFAULT 0 |
| `matched_count` | INT | NOT NULL DEFAULT 0 |
| `amount_mismatch_count` | INT | NOT NULL DEFAULT 0 |
| `missing_internal_count` | INT | NOT NULL DEFAULT 0 |
| `missing_external_count` | INT | NOT NULL DEFAULT 0 |
| `duplicate_count` | INT | NOT NULL DEFAULT 0 |
| `created_at`/`updated_at`/`created_by` | defaults |

### 15. `reconciliation_lines`
One row per settlement line in the CSV.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `batch_id` | UUID FK→reconciliation_batches.id | NOT NULL |
| `external_reference` | VARCHAR(128) | NOT NULL |
| `external_amount` | Numeric(12,2) | NOT NULL |
| `student_id` | UUID FK→students.id | NULL |
| `payment_id` | UUID FK→payments.id | NULL |
| `classification` | VARCHAR(24) | NOT NULL CHECK in (MATCHED, AMOUNT_MISMATCH, MISSING_INTERNAL, MISSING_EXTERNAL, DUPLICATE) |
| `notes` | TEXT | NULL |
| `created_at` | TIMESTAMP | default |

Index on `batch_id`, `(external_reference)`.

### 16. `idempotency_keys`
Dedicated table so idempotency spans more than just payments (e.g. reversal
requests, reconciliation batches) and so the DB constraint is the enforcer.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK |
| `key` | VARCHAR(128) | **UNIQUE** NOT NULL |
| `entity_type` | VARCHAR(64) | NOT NULL |
| `entity_id` | UUID | NULL |
| `expires_at` | TIMESTAMP | NULL |
| `created_at` | TIMESTAMP | default |

### 17. `audit_logs`
Append-only. Every state transition writes here.

| Column | Type | Constraints |
|---|---|---|
| `id` | BIGSERIAL | PK |
| `actor_user_id` | UUID FK→users.id | NULL (NULL = system) |
| `action` | VARCHAR(128) | NOT NULL |
| `entity_type` | VARCHAR(64) | NOT NULL |
| `entity_id` | VARCHAR(64) | NOT NULL |
| `ts` | TIMESTAMP | NOT NULL DEFAULT now() |
| `metadata` | JSON | NULL |

Indexes: `(entity_type, entity_id)`, `actor_user_id`, `ts`.

## Relationships (ER summary)

```
departments 1───∞ programs 1───∞ students
fee_heads 1───∞ fee_structure_lines ∞──1 fee_structures ∞──1 programs
fee_structures 1───∞ student_fee_assignments ∞──1 students
student_fee_assignments 1───∞ installments
students 1───∞ concessions ∞──1 fee_heads / installments
students 1───∞ payments 1───∞ payment_allocations ∞──1 installments
payments 1───∞ payment_reversals
reconciliation_batches 1───∞ reconciliation_lines
users 1───∞ audit_logs (actor)
users 1──1 students (STUDENT role only)
```

## Why each constraint exists (rationale)

| Constraint | Why |
|---|---|
| `payments.gateway_ref UNIQUE` | Gateway idempotency: a gateway callback fires once per ref; duplicates are rejected at the DB, not at the service. Invariant #3. |
| `payments.idempotency_key UNIQUE` | Client-supplied idempotency for retry-safe payment initiation. Invariant #3. |
| `payments.method='ONLINE' ⇒ gateway_ref NOT NULL` | An online payment without a gateway reference is a bug. |
| `payments.amount CHECK > 0` | A non-positive payment is meaningless. |
| `payment_allocations.amount CHECK > 0` | Same. |
| `(payment_id, installment_id, fee_head_id) UNIQUE` | An allocation double-charges a head on an installment for a payment; prevented at DB. |
| `installments.status CHECK in (...)` | State machine validity; the cache must be one of the legal states. |
| `installments (assignment, number) UNIQUE` | Prevents duplicate installment numbering. |
| `student_fee_assignments (student, year) UNIQUE` | One fee assignment per student per year; re-assignment is a new row, not an edit. |
| `fee_structure_lines (structure, head) UNIQUE` | A head can't be priced twice in the same structure. |
| `concessions.status CHECK in (...)` | Workflow validity. |
| `audit_logs` append-only + indexed by `(entity_type, entity_id)` | Auditability + fast lookup by entity. |
| `created_by` on every financial table | Non-repudiation: who created the record. |
| `outstanding_balance` is **not stored** | Invariant #6: derived truth only. The integrity checker enforces honesty. |
| `installments.status` is a cache, verified by integrity checker | Speed for dashboards + verifiable honesty. |
| Postgres trigger `trg_allocation_within_payment` | DB-level enforcement that `Σ allocations ≤ payment.amount`. Service + checker are belt-and-suspenders. |

## Cross-row invariants (enforced in service + integrity checker, documented here)

1. `Σ payment_allocations.amount` for a payment `≤ payments.amount`.
2. `Σ payment_reversals.amount` for a payment `≤ payments.amount`.
3. `Σ allocations` for an installment `≤ installment.amount − Σ approved concessions on that installment`.
4. A payment in status `SUCCESS` has at least one allocation (post-success) *unless* it is unallocated-by-design (cash pending allocation) — flagged by `metadata.unallocated = true`. The integrity checker allows this state.
5. A `REVERSED` payment has a linked `payment_reversals` row with `status='COMPLETED'`.
