# EduPay — Enterprise Fee Collection & Financial Reconciliation System

EduPay is a production-ready, financial-grade college fee management system built with **FastAPI**, **SQLAlchemy 2**, **PostgreSQL**, and **Next.js 16**. Designed for academic institutions (≈5,000 students, 200 staff), it enforces strict double-entry ledger principles, automated payment reconciliation, multi-role authorization (RBAC), and real-time auditability with zero-drift financial integrity verification.

---

## 🚀 Quickstart Guide

### Option 1: One-Click Local Setup (Recommended for Evaluation)

Execute the interactive local runner script. It automatically installs dependencies, applies Alembic migrations, seeds 300+ student accounts & payment structures, and launches both backend and frontend servers.

#### Windows (PowerShell):
```powershell
.\start-local.ps1
```

#### Linux / macOS (Bash):
```bash
chmod +x start-local.sh
./start-local.sh
```

- **Frontend SPA**: [http://localhost:3000](http://localhost:3000)
- **Backend API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Option 2: Docker Compose (Production Setup)

Spin up the entire stack including PostgreSQL 16 container, backend API service, and Next.js frontend with containerized health checks:

```bash
docker compose up --build
```

---

## 🔑 Demo Credentials

The seeded database includes pre-configured accounts across all system roles (all passwords: `Password123!`):

| Role | Email | Permissions & View Access |
|---|---|---|
| **System Admin** | `admin@edupay.college` | Full System Access, Chaos Panel, User Management, Audit Logs, Integrity Check |
| **Finance Manager** | `manager@edupay.college` | Financial Dashboards, Reversal Approvals, Reconciliation Classifier, Audit Logs |
| **Finance Staff** | `staff@edupay.college` | Student Account Lookup, Counter Payments, Payment History |
| **Student** | `student@edupay.college` | Personal Fee Breakdown, Installment Schedules, Payment History |

*Note: 300 additional student accounts (`stu20240001@edupay.college` – `stu20240300@edupay.college`) are seeded with realistic fee structure assignments.*

---

## 📐 Non-Negotiable Financial Invariants

1. **Exact Decimal Precision**: All monetary fields use `NUMERIC(12,2)`. Floating-point math is strictly forbidden across both backend and frontend.
2. **Derived Outstanding Balance**: Outstanding balances are derived dynamically (`Invoices − Concessions − Payment Allocations`). Cached installment statuses are continuously validated against derived truth.
3. **Immutable Payment Ledger**: Payment records cannot be modified or deleted post-settlement (`SUCCESS`). Financial adjustments are strictly executed via linked `Reversal` records with manager approval.
4. **Database-Level Idempotency**: Idempotency is enforced via `UNIQUE` constraints at the PostgreSQL database level (`idempotency_key`, `gateway_ref`), preventing double-charging under network retries or concurrent webhook callbacks.
5. **Comprehensive Audit Logs**: Every state change, financial allocation, and status transition automatically writes an immutable record to `audit_logs` capturing actor, timestamp, IP, and payload diffs.

---

## 🧪 Test Suite & Integrity Verification

EduPay includes an automated pytest suite (50 test cases) covering auth RBAC, state machine transitions, concurrent webhook handling, idempotency replays, reconciliation classification, and mathematical integrity checks.

### Running Backend Tests:

#### Windows (PowerShell):
```powershell
.\run-tests.ps1
```

#### Linux / macOS (Bash):
```bash
./run-tests.sh
```

---

## 💻 Tech Stack Architecture

### Backend API (`/backend`)
- **Framework**: FastAPI (Python 3.12) with Pydantic v2 validation.
- **ORM & Database**: SQLAlchemy 2.0 with PostgreSQL (cross-compatible SQLite fallback for zero-config local runs).
- **Database Migrations**: Alembic version-controlled schema upgrades.
- **Authentication & Security**: JWT tokens (RS256/HS256) with bcrypt password hashing and Role-Based Access Control (RBAC).

### Frontend Application (`/src`)
- **Framework**: Next.js 16 (App Router) with TypeScript & React 19.
- **UI Design System**: Tailwind CSS v4, shadcn/ui components, Framer Motion micro-animations, and Sonner notifications.
- **Financial Visualization**: Custom CSS-based KPI cards and analytics bars (no bulky chart library overhead).

---

## 🛡️ Core Functional Modules

- 📊 **Finance Executive Dashboard**: Real-time KPI summaries, payment method breakdowns, and collection analytics.
- 🎓 **Student Account Hub**: Comprehensive search, fee breakdown by installment, concession history, and allocation logs.
- 💳 **Payment Engine**: Multi-channel payments (Cash, Cheque, Online Gateway) with explicit 9-state machine transitions and online webhook handling.
- 🔄 **Automated Reconciliation**: Multi-line bank CSV parser classifying transactions into 5 categories: `MATCHED`, `AMOUNT_MISMATCH`, `MISSING_INTERNAL`, `MISSING_EXTERNAL`, and `DUPLICATE`.
- 🕵️ **Integrity Verification**: Real-time mathematical auditor checking zero-drift between cached status flags and derived financial equations.
- ⚡ **Chaos Simulator Panel**: Dev-only gateway emulator for testing timeout delays, dropped callbacks, duplicate webhook spikes, and edge failures.

---

## 📄 License & Attribution

Developed for assessment and production engineering evaluation. Codebase structure adheres to clean architecture principles and enterprise backend standards.
