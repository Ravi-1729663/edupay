# EduPay — Final Assessment Submission Report

## Executive Summary

**Status: Implementation complete and validated against the included automated test suite.**

EduPay is a production-oriented student fee collection and reconciliation platform developed for **Edumerge Product Engineering Assessment — Assignment 2**.

The system addresses fee obligations, multiple fee heads, concessions, installments, payments, payment failures, duplicate callbacks, reversals, outstanding balances, reconciliation exceptions, auditability, role-based access control, and financial integrity.

### Validation Summary

* **Backend:** 50/50 Pytest tests passing
* **Frontend:** Next.js 16 + TypeScript + Tailwind CSS build completed successfully
* **Financial integrity:** Integrity checker passes against seeded data
* **Database:** PostgreSQL 16 with `NUMERIC(12,2)` monetary fields
* **Concurrency:** Duplicate webhook handling validated with concurrent test execution
* **Reconciliation:** CSV-based settlement classification implemented
* **RBAC:** ADMIN, FINANCE_MANAGER, FINANCE_STAFF, and STUDENT roles
* **Local execution:** Windows PowerShell, Linux/macOS Bash, and Docker Compose launchers included

## 1. Working Solution

EduPay provides four role-specific experiences:

| Role            | Primary Capabilities                                                           |
| --------------- | ------------------------------------------------------------------------------ |
| ADMIN           | System administration, RBAC, integrity checker, audit logs, gateway simulation |
| FINANCE_MANAGER | Financial dashboard, reconciliation, reversal approval, audit review           |
| FINANCE_STAFF   | Student fee lookup, counter payments, payment records                          |
| STUDENT         | Fee breakdown, installment schedule, payment history                           |

### Quickstart

**Windows PowerShell**

```powershell
.\start-local.ps1
```

**Linux/macOS**

```bash
chmod +x start-local.sh
./start-local.sh
```

**Dockerized evaluation environment**

```bash
docker compose up --build
```

### Local Endpoints

* Frontend: `http://localhost:3000`
* Backend Swagger: `http://localhost:8000/docs`

Demo credentials are documented in the repository README.

## 2. Architecture

EduPay uses a **modular monolith** architecture:

```text
Next.js 16 Frontend
        │
        │ REST API
        ▼
FastAPI Backend
        │
 ┌──────┼─────────────────────┐
 │      │          │           │
Auth  Payment   Recon       Integrity
 │      │          │           │
 └──────┴──────────┴───────────┘
                │
                ▼
          PostgreSQL 16
```

The backend separates API, schema, persistence, and domain-service responsibilities while avoiding unnecessary distributed-system complexity for the assessment scope.

## 3. Financial Model

Financial truth is derived from authoritative records rather than maintained as a mutable balance field.

Conceptually:

**Outstanding Balance = Fee Obligations − Approved Concessions − Successful Allocations + Applicable Reversal Effects**

Monetary values use:

* Python `Decimal`
* PostgreSQL `NUMERIC(12,2)`

IEEE-754 floating-point arithmetic is not used for financial calculations.

Successful financial transactions are immutable. Corrections are represented through linked reversal records rather than modifying or deleting the original successful transaction.

## 4. Payment Lifecycle

The system explicitly models payment states and validates state transitions.

The mock gateway supports controlled failure scenarios including:

* SUCCESS
* FAILED
* TIMEOUT / NO CALLBACK
* DUPLICATE CALLBACK
* LATE CALLBACK

This makes asynchronous payment behaviour demonstrable without depending on an external payment provider.

Idempotency is enforced at the database layer rather than relying solely on an application-level existence check.

## 5. Payment Allocation

Payments are allocated using a deterministic strategy:

1. Oldest due unpaid installment first
2. Fee-head priority as the tie-breaker
3. Partial allocations supported
4. Over-allocation prevented

Allocation records preserve the relationship between a payment and the underlying fee obligation.

## 6. Reconciliation

Finance managers can upload settlement data and compare external settlement records against internal successful payments.

The reconciliation engine identifies:

1. `MATCHED`
2. `AMOUNT_MISMATCH`
3. `MISSING_INTERNAL`
4. `MISSING_EXTERNAL`
5. `DUPLICATE`

Exceptions are classified for review rather than silently modifying financial records.

A reconciliation mismatch therefore does **not** automatically change the internal financial truth.

## 7. Financial Integrity & Concurrency

Important validation scenarios include:

### Duplicate webhook race

Two identical callbacks arriving concurrently must not create two financial transactions.

The implementation combines:

* Database uniqueness constraints
* Transaction boundaries
* Row-level locking where applicable
* Concurrent test execution

### Reversal protection

The system prevents:

* Reversing more than the original payment amount
* Reversing an already reversed payment
* Invalid state transitions
* Unauthorized reversal approval

### Integrity Checker

The integrity checker validates financial invariants including:

* Allocation does not exceed payment amount
* Allocation does not exceed the applicable obligation
* Reversal does not exceed the reversible amount
* Payment state transitions remain valid
* Duplicate external references are prevented
* Derived balances remain internally consistent

## 8. Auditability

Meaningful financial actions and state changes are recorded with audit information such as:

* Actor
* Action
* Entity
* Timestamp
* Previous state
* New state
* Relevant metadata

This allows financial operations to be investigated without relying exclusively on mutable application records.

## 9. Engineering Trade-offs

### PostgreSQL + SQLite

PostgreSQL is the authoritative production/evaluation database because the financial integrity and concurrency model relies on PostgreSQL transaction semantics.

SQLite support is provided for lightweight local development where appropriate.

Concurrency-specific guarantees are validated against PostgreSQL.

### Synchronous reconciliation

Reconciliation is intentionally synchronous for the assessment scope. This provides immediate feedback to finance users while avoiding unnecessary worker infrastructure.

### Custom dashboard visualizations

Simple CSS-based analytics components are used instead of introducing a heavyweight charting dependency for a relatively small dashboard.

## 10. Repository Structure

```text
backend/
├── alembic/
└── app/
    ├── api/
    ├── core/
    ├── db/
    ├── models/
    ├── schemas/
    ├── services/
    └── tests/

src/
├── app/
├── components/edupay/
└── lib/

docs/
├── SPEC.md
├── DECISIONS.md
├── DATA_MODEL.md
└── API.md

docker-compose.yml
start-local.ps1
start-local.sh
run-tests.ps1
run-tests.sh
```

## 11. AI Usage

AI-assisted development was used as permitted by the assessment instructions.

AI was primarily used for:

* Initial architecture and implementation assistance
* Backend domain services
* Frontend component generation
* Database migrations
* Validation schemas
* Test scaffolding
* Local launcher scripts

Generated code was manually inspected, executed, tested, and corrected where required.

One concrete issue identified during validation was an Alembic path-resolution error when tests were executed from the repository root. The initial relative migration path failed outside the backend working directory.

The issue was identified through actual test execution and corrected by resolving the Alembic script location from the test configuration's absolute filesystem path.

The final test suite was then rerun successfully.

## 12. Validation Philosophy

The implementation was validated through execution rather than relying solely on generated code inspection.

Particular attention was given to:

* Database constraints
* Financial arithmetic
* State transitions
* Idempotency
* Concurrent callbacks
* Authorization
* Reconciliation classification
* Reversal rules
* Migration execution
* Cross-platform startup

The objective was not simply to build screens that record payments, but to model the financial lifecycle and failure scenarios that make fee collection systems difficult to implement reliably.