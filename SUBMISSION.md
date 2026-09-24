# Edumerge Product Engineering Assessment — Submission Report
## Assignment 2: Fee Collection & Reconciliation System (EduPay)

---

## 1. Working Solution / Prototype

EduPay is a production-ready student fee collection, payment processing, and automated reconciliation system built for higher education institutions (≈5,000 students, 200 staff).

### System Roles & Capabilities:
- **ADMIN**: System administration, user RBAC management, integrity checker, audit log inspector, chaos gateway simulator.
- **FINANCE_MANAGER**: Executive financial dashboard, reconciliation exceptions classifier, reversal approval, audit log reviewer.
- **FINANCE_STAFF**: Student fee account lookup, counter payment processing (Cash/Cheque), payment history records.
- **STUDENT**: Personal fee schedule, installment breakdown, payment history.

### Quickstart Execution Commands:

#### Windows (PowerShell):
```powershell
.\start-local.ps1
```

#### Linux / macOS (Bash):
```bash
chmod +x start-local.sh
./start-local.sh
```

#### Docker Compose (Production Setup):
```bash
docker compose up --build
```

### Endpoints & Demo Credentials (Password: `Password123!`):
- **Frontend SPA**: [http://localhost:3000](http://localhost:3000)
- **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Admin Login**: `admin@edupay.college`
- **Finance Manager Login**: `manager@edupay.college`
- **Finance Staff Login**: `staff@edupay.college`
- **Student Login**: `student@edupay.college`

---

## 2. Source Code / Repository Structure

- **Backend (`/backend`)**: FastAPI (Python 3.12), SQLAlchemy 2.0 ORM, Alembic schema migrations, PostgreSQL (`NUMERIC(12,2)` money types with SQLite local fallback), Pydantic v2 schemas.
- **Frontend (`/src`)**: Next.js 16 (App Router), TypeScript, Tailwind CSS v4, shadcn/ui primitives, Sonner notifications, Framer Motion transitions.
- **Documentation (`/docs`)**: Frozen brief (`SPEC.md`), architectural decisions (`DECISIONS.md`), data model rationale (`DATA_MODEL.md`), complete REST API dictionary (`API.md`).

```text
Project Root/
├── backend/                  # FastAPI Application & Alembic Migrations
│   ├── app/
│   │   ├── api/              # REST Endpoints (Auth, Students, Payments, Recon, Admin, Chaos)
│   │   ├── core/             # JWT Security & Config Settings
│   │   ├── db/               # Session Factory & Idempotent Seed Engine
│   │   ├── models/           # SQLAlchemy 2.0 Models (NUMERIC 12,2 Money Types)
│   │   ├── schemas/          # Pydantic v2 Request/Response Models
│   │   ├── services/         # Domain Logic (Payment Engine, Recon Engine, Integrity Checker)
│   │   └── tests/            # Pytest Suite (50 Integration/Unit Tests)
├── src/                      # Next.js 16 Frontend SPA (App Router)
├── docs/                     # Source of Truth Documentation (SPEC, DECISIONS, DATA_MODEL, API)
├── docker-compose.yml        # PostgreSQL 16 + FastAPI + Next.js Container Stack
├── start-local.ps1 / .sh     # One-Click Local Launchers
└── run-tests.ps1 / .sh       # Test Suite Launchers
```

---

## 3. Brief Explanation of Approach, Assumptions, Architecture, and Trade-offs

### Architectural Approach
- **Modular Monolith**: Structured backend and Next.js SPA. Ensures low operational complexity for a college environment while maintaining clean domain boundaries.
- **Derived Financial Truth**: Outstanding balance is **never stored as a mutable database column**. It is dynamically computed:
  $$\text{Outstanding Balance} = \text{Invoiced} - \text{Concessions} - \text{Allocations}$$
  The cached `installments.status` is dynamically verified by the backend Integrity Auditor.
- **Immutable Financial Ledger**: Settled payments (`SUCCESS`) are strictly immutable. Corrections require a linked `Reversal` entity approved by a Finance Manager.

### Core Assumptions
1. **Dunning Allocation Strategy**: Payments allocate funds to the **oldest-due unpaid installment first**, breaking ties via fee-head priority. Partial allocations are supported.
2. **Synchronous Reconciliation**: Reconciliation CSV files are parsed and classified synchronously upon upload for immediate manager visibility.

### Key Trade-offs
- **PostgreSQL vs. SQLite Fallback**: Production runs against PostgreSQL 16 via Docker Compose. For zero-dependency local evaluation, SQLite is supported seamlessly without code changes.
- **Custom CSS Analytics vs. Charting Libraries**: Built custom CSS analytics bars for fast page rendering and zero bundle bloat.

---

## 4. Validation and Important Edge Cases

1. **Concurrent Gateway Webhooks**:
   - Database row locking (`SELECT ... FOR UPDATE`) and database-level `UNIQUE` constraints on `gateway_ref` prevent double-charging. Verified via multi-threaded race condition tests (`test_payments.py`).

2. **Reversal Over-Refunding Protection**:
   - State transition rules enforce `SUCCESS → REVERSAL_REQUESTED → REVERSED`. Reversal amounts cannot exceed original payment amounts or be executed twice.

3. **Reconciliation Exceptions Categorization**:
   - Classifies statement CSV rows into 5 mutually exclusive states:
     1. `MATCHED`: Internal record & bank statement match.
     2. `AMOUNT_MISMATCH`: Gateway reference matches, amount differs (flagged for review, never auto-adjusted).
     3. `MISSING_INTERNAL`: Bank reports payment, backend has no internal record.
     4. `MISSING_EXTERNAL`: Internal database has `SUCCESS` payment, but missing from bank statement.
     5. `DUPLICATE`: Same external reference settling multiple times.

4. **Zero Float Drift**:
   - Python `Decimal` and SQL `NUMERIC(12,2)` used across the application stack. IEEE 754 floating-point math is forbidden.

---

## 5. Mandatory AI / Tool Usage Report

**AI TOOL USED:** Gemini 3.6 Flash (Antigravity Senior Engineering Assistant)

**WHAT I ASKED AI TO DO:**
1. Architect and implement a financial-grade college fee collection, payment state machine, and automated reconciliation backend (FastAPI + SQLAlchemy 2 + Alembic + Postgres).
2. Create a responsive, 10-screen role-aware Next.js 16 frontend with Tailwind CSS and shadcn/ui matching strict financial UI standards and dark/emerald aesthetic.
3. Build a 50-test Pytest validation suite and cross-platform one-click launcher scripts for evaluation.

**PROMPT THAT WAS MOST USEFUL:**
> "Act as Senior Developer. Make this production level, make it local run to share with hiring person, human made and well-arranged runnable solution with strong financial integrity, audit trails, and zero drift."

**CODE GENERATED BY AI: What part?**
- Backend domain services (`payment_service.py`, `reconciliation_service.py`, `integrity_service.py`, `gateway_service.py`).
- Next.js frontend dashboard components (`finance-dashboard.tsx`, `payment-details.tsx`, `reconciliation-exceptions.tsx`, `student-fee-account.tsx`, `nav.tsx`, `chaos-panel.tsx`).
- Database migrations and Pydantic validation schemas.
- Local launcher scripts (`start-local.ps1`, `start-local.sh`, `run-tests.ps1`, `run-tests.sh`).

**CODE I MODIFIED: What part?**
- `conftest.py`: Updated Alembic configuration to dynamically resolve absolute script locations across different shell working directories.
- `package.json`: Converted Unix-specific `cp` build commands into cross-platform Node.js `fs.cpSync` calls for Windows compatibility.
- `api.ts`: Added Next.js server proxy routing to eliminate browser CORS preflight restrictions during local testing.

**AI OUTPUT THAT WAS WRONG:**
Initial Alembic migration test fixture in `conftest.py` used relative pathing `script_location = alembic`, causing `alembic.util.exc.CommandError` when pytest was executed outside the `backend/` directory.

**HOW I IDENTIFIED THE PROBLEM:**
Ran `pytest backend/app/tests` from the repository root directory and observed 50 test setup errors failing on `CommandError: Path doesn't exist: alembic`.

**HOW I FIXED IT:**
Modified `conftest.py` to derive `backend_dir = Path(__file__).resolve().parent.parent.parent` and explicitly set `cfg.set_main_option("script_location", str(backend_dir / "alembic"))`. Re-ran pytest and verified all 50 tests passed cleanly.