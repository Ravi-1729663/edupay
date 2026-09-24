# BUGS.md — EduPay frontend ↔ backend API drift log

> Source of truth: `docs/API.md` + the Task D brief (which restates the
> exact endpoint shapes the implemented backend exposes). The backend
> remains untouched; the frontend adapts.

## No API drift detected — frontend matches docs/API.md and the implemented backend schemas.

The Package D frontend was written directly against the Task D brief's
"EXACT API endpoints + response shapes" section, which is the most
up-to-date statement of the contract (newer than `docs/API.md`).
Where the brief and `docs/API.md` differ, the brief wins and the
frontend follows it. The differences between the two documents are
themselves documented here for transparency — they are NOT drifts from
the implemented backend (the backend follows the same shapes the brief
lists, as confirmed by Packages A/B/C worklog entries):

### Minor doc-vs-brief reconciliations (not drift)

1. **`POST /payments/initiate` response field**
   - `docs/API.md` writes the redirect URL field as `gateway_redirect_url`.
   - Task D brief writes it as `redirect_url`.
   - The implemented backend (Package B worklog) returns `redirect_url`.
   - Frontend uses `redirect_url` (matches brief + backend). No drift.

2. **`GET /admin/audit-logs` response field**
   - `docs/API.md` and Task D brief both list `{items, limit, offset}` —
     no `total` field.
   - Frontend types `AuditPage.total?` as optional and the
     `PaginationBar` falls back to `pageItems.length` when `total` is
     missing, so pagination works without a server-side count.
   - No drift; the frontend simply doesn't rely on a `total` that
     doesn't exist.

3. **`GET /departments`, `/programs`, `/fee-heads`, `/fee-structures`**
   - `docs/API.md` writes some as `{items:[...]}` pages; the Task D brief
     writes them as plain arrays.
   - Frontend uses `T[]` array types for these. The implemented backend
     (Package A worklog) returns plain arrays. No drift.

4. **`POST /payments/counter` request body — `allocate_to`**
   - Both `docs/API.md` and the brief list `allocate_to` as optional
     (auto-allocation kicks in when omitted). Frontend does not yet
     build a counter-payment UI in Package D (the brief does not require
     it for the screens listed). The shape is correctly typed and ready
     for a future Package E to consume.
