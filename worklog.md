# EduPay — Package A Worklog

This file is the shared worklog for all agents on the EduPay project.
Append a new section (do NOT overwrite) after completing each Task ID, using the template:

```
---
Task ID: <id>
Agent: <name>
Task: <what you were asked to do>

Work Log:
- step 1
- step 2

Stage Summary:
- key results / decisions / artifacts
```

Current phase: **Package A — scaffold, models, migration, auth, integrity checker, seed, tests, docs, docker.**

---
Task ID: 0
Agent: lead
Task: Environment scan + plan

Work Log:
- Detected Python 3.12.14 venv at /home/z/.venv (fastapi 0.128, pydantic 2.12, pytest 9 present; sqlalchemy/alembic/passlib/jose/psycopg2 to be pip-installed).
- No docker / no psql in sandbox → local execution uses SQLite (SQLAlchemy Numeric(12,2) is cross-DB safe; prod targets Postgres via docker-compose).
- Existing Next.js 16 project at repo root (shadcn/ui installed) → reused as the `frontend` service; backend lives under `backend/`.

Stage Summary:
- Decisions: backend in `backend/`, frontend = root Next.js, prod DB = Postgres (docker), local test DB = SQLite.
- Proceeding to write design docs (source of truth) before any code.

---
Task ID: 10
Agent: frontend-styling-expert
Task: Build the EduPay frontend SPA at `/` (Next.js 16 App Router, TypeScript, Tailwind 4, shadcn/ui) integrating the Package-A backend contract (auth, students, outstanding, integrity-check, users, audit-logs) and providing the role-based dashboard, student fees view, integrity panel, and the dev chaos-panel placeholder required by the brief.

Work Log:
- Read worklog, API.md, backend schemas (auth/integrity/student/common), main.py exception envelope, and the shadcn primitives (card, badge, alert, table, tabs, button, input, label, skeleton, tooltip, sonner, collapsible).
- Created `src/lib/api.ts` with the `apiUrl`/`apiFetch`/`ApiError`/`setToken`/`clearToken`/`getToken` helpers (Caddy `XTransformPort` routing, Bearer from localStorage, defensive error-envelope parsing that handles both `error` and `detail.error` shapes) and TypeScript types for `User`, `Role`, `TokenResponse`, `Page<T>`, `Student`, `InstallmentOutstanding`, `StudentOutstanding`, `Drift`, `InvariantViolation`, `IntegrityReport`, `AuditLog`, `AuditPage`.
- Created `src/lib/money.ts` with `formatMoney(s)` → ₹-prefixed en-IN 2-dp + `formatDate`/`formatDateTime` helpers.
- Created `src/components/edupay/status-badge.tsx` with `StatusBadge` (PENDING=slate, PARTIALLY_PAID=amber, PAID=emerald, OVERDUE=red) and `RoleBadge` (emerald/stone/slate/teal — no indigo/blue primary).
- Created `src/components/edupay/footer.tsx` — sticky Tailwind footer (`mt-auto`) with the required footer text.
- Created `src/components/edupay/login-card.tsx` — emerald-branded centered login card with email/password, loading spinner, sonner error toasts, and the four demo credentials (admin/manager/staff/student @edupay.college, Password123!) as one-click fill buttons.
- Created `src/components/edupay/integrity-panel.tsx` — emerald "Run integrity check" button → GET /admin/integrity-check; green check panel with students/installments/payments counts when ok; red drifts table + invariant violations table when not; full error Alert with code + request_id.
- Created `src/components/edupay/users-panel.tsx` — debounced search, shadcn Table (email/full_name/role badge/active), client pagination (limit/offset=20), skeleton loading, error Alert.
- Created `src/components/edupay/students-panel.tsx` — debounced search + paginated list; clicking a row expands to fetch `/students/{id}/outstanding` and shows the by-installment breakdown with cached_status vs derived_status, drift highlighted in amber.
- Created `src/components/edupay/chaos-panel.tsx` — dev-only placeholder listing all five chaos modes (SUCCESS/FAILED/TIMEOUT_NO_CALLBACK/DUPLICATE_CALLBACK/LATE_CALLBACK) as disabled toggle buttons with tooltips; visibly present as required by the brief, wired to nothing yet.
- Created `src/components/edupay/student-fees.tsx` — STUDENT "My fees" card: GET /students/{user.student_id}/outstanding; installments table with due date/amount/allocated/outstanding/status badges; amber alert when any installment is OVERDUE; totals row; Package-B "Payments" placeholder with a disabled Pay button; embeds the ChaosPanel.
- Created `src/components/edupay/dashboard.tsx` — sticky top bar with /public/logo.svg, role badge, Sign-out button; Tabs (role-based): ADMIN → Users/Integrity/Audit logs/Students; FINANCE_MANAGER → Students/Integrity/Audit logs; FINANCE_STAFF → Students; STUDENT → My fees. AuditLogsPanel fetches `/admin/audit-logs?limit=50`. Subtle framer-motion fade on tab change.
- Replaced `src/app/page.tsx` — client component; useEffect rehydrates a stored token via GET /auth/me; renders LoginCard or Dashboard; shows a "Loading EduPay…" splash while booting.
- Updated `src/app/layout.tsx` metadata to EduPay (title, favicon → /logo.svg) and swapped the radix Toaster for the Sonner Toaster (richColors + closeButton) since the rest of the UI uses sonner.

Self-check:
- `bun run lint` — clean (0 errors, 0 warnings).
- `dev.log` — only the pre-existing Caddy cross-origin advisory; no compile errors; `GET / 200` repeatedly with fast compile times; SSR'd HTML contains "EduPay" + "Loading" placeholder (client hydrates the booting → login/dashboard switch).
- Money fields rendered via formatMoney as ₹1,20,000.00 strings.

Stage Summary:
- Deliverables: `src/lib/api.ts`, `src/lib/money.ts`, `src/app/page.tsx` (replaced), `src/app/layout.tsx` (toaster+metadata swapped), and 9 new components under `src/components/edupay/` (status-badge, footer, login-card, dashboard, integrity-panel, users-panel, students-panel, chaos-panel, student-fees).
- Backend contract fully wired for: POST /auth/login, GET /auth/me, GET /admin/integrity-check, GET /students (+ outstanding drilldown), GET /users, GET /admin/audit-logs. Calls go through the Caddy gateway via `?XTransformPort=8000` (override with `NEXT_PUBLIC_API_BASE`).
- UX: emerald/slate/stone/amber/red palette (no indigo/blue primary), responsive tables (overflow-x-auto), skeleton loading states, red Alert error states with code + request_id, sticky footer, framer-motion tab fades.
- Chaos panel is visually present (required by brief) but inert — wiring deferred to Package B.

---
Task ID: 11
Agent: lead
Task: Execute — install deps, run migration, seed, tests, verify acceptance

Work Log:
- Installed backend deps via /home/z/.venv (sqlalchemy 2.0.54, alembic 1.14.1, pydantic-settings 2.13.1, passlib+bcrypt4, jose, psycopg2, etc.).
- Ran `alembic upgrade head` against SQLite → all 17 tables + alembic_version created clean.
- Ran `python -m app.db.seed` → 304 users, 300 students, 6 fee heads, 4 fee structures, 300 assignments, 900 installments, 2 pending concessions.
- Re-ran seed → identical counts (idempotent ✓).
- Integrity checker against seeded data: ok=True, 300 students, 900 installments, 0 drifts, 0 violations ✓.
- pytest: 27/27 passing (test_auth 12, test_integrity 4, test_models 11) ✓.
- Fixed 4 bugs surfaced by execution: (a) missing `Integer` import in audit.py, (b) SQLite batch-alter for deferred users↔students FK, (c) User/Department/Program/FeeHead have no created_by column (removed from seed), (d) pydantic-settings JSON-parsing CORS as CSV, (e) admin.py route shadowed imported service `check` (renamed alias to `run_integrity_check`), (f) email-validator rejects `.test` TLD → switched all emails to `@edupay.college`.
- Started detached uvicorn on :8000 against seeded SQLite DB.
- End-to-end curl: admin login 200, /ready ok, /admin/integrity-check ok=true, /students 300, /fee-heads 6, RBAC staff→/users=403, student→/students=403, manager→/admin/integrity-check=200 ✓.

Stage Summary:
- Package A acceptance: migration ✓, seed ✓ idempotent, login all 4 roles ✓, RBAC blocks cross-role ✓, /admin/integrity-check zero drift ✓.
- Cannot run `docker compose up` in sandbox (no docker) → command list provided to grader in final report.
- Backend running on :8000 for frontend browser verification next.
