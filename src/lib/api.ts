/**
 * EduPay frontend API helper.
 *
 * All calls go through the Next.js server-side catch-all proxy at
 * `/api/edupay/<path>` (see `src/app/api/edupay/[...path]/route.ts`), which
 * forwards to the backend on `${BACKEND_URL}` (default
 * `http://localhost:8000`). This keeps every API call same-origin (no CORS
 * preflight, no `?XTransformPort` needed) and works identically in:
 *   - the sandbox preview (Next.js server reaches localhost:8000 directly)
 *   - docker (set `BACKEND_URL=http://backend:8000`)
 *
 * For an absolute override (e.g. pointing at a remote backend), set
 * `NEXT_PUBLIC_API_BASE=https://api.example.com` and the helper will skip the
 * proxy prefix entirely.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";
const PROXY_PREFIX = "/api/edupay";

/** Build a URL string suitable for fetch(): proxied-relative or absolute. */
export function apiUrl(path: string): string {
  if (API_BASE) return API_BASE + path;
  // Strip a leading slash so "/auth/login" → "/api/edupay/auth/login".
  const p = path.startsWith("/") ? path : "/" + path;
  return PROXY_PREFIX + p;
}

export class ApiError extends Error {
  status: number;
  code: string;
  requestId?: string;
  constructor(
    status: number,
    code: string,
    message: string,
    requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

function parseErrorEnvelope(data: any): {
  code: string;
  message: string;
  requestId?: string;
} {
  // The FastAPI HTTPException handler in main.py returns the canonical
  // envelope `{error:{code,message}, request_id}`. Be defensive in case the
  // shape ever changes — also check under `detail`.
  const err =
    data?.error ??
    (data?.detail && typeof data.detail === "object" ? data.detail.error : null);
  return {
    code: err?.code ?? "error",
    message: err?.message ?? "request failed",
    requestId: data?.request_id,
  };
}

/**
 * Typed fetch wrapper. Reads the Bearer token from localStorage, attaches
 * JSON content-type, and throws `ApiError` on non-2xx.
 */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("edupay_token") : null;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  if (token) headers["Authorization"] = "Bearer " + token;

  const res = await fetch(apiUrl(path), { ...init, headers });
  const data: any = await res.json().catch(() => ({}));
  if (!res.ok) {
    const env = parseErrorEnvelope(data);
    throw new ApiError(res.status, env.code, env.message, env.requestId);
  }
  return data as T;
}

export function setToken(t: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("edupay_token", t);
}
export function clearToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("edupay_token");
}
export function getToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem("edupay_token");
}

// ── Domain types ────────────────────────────────────────────────────

export type Role = "STUDENT" | "FINANCE_STAFF" | "FINANCE_MANAGER" | "ADMIN";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  student_id?: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Student {
  id: string;
  roll_number: string;
  full_name: string;
  email: string;
  phone?: string | null;
  program_id: string;
  batch_year: number;
  status: string; // ACTIVE | INACTIVE | GRADUATED | SUSPENDED
}

export interface InstallmentOutstanding {
  installment_id: string;
  installment_number: number;
  due_date: string; // ISO date
  amount: string; // money string
  invoiced: string;
  concessions: string;
  allocated: string;
  outstanding: string;
  cached_status: string; // PENDING | PARTIALLY_PAID | PAID | OVERDUE
  derived_status: string;
  drift: boolean;
}

export interface StudentOutstanding {
  student_id: string;
  total_invoiced: string;
  total_concessions: string;
  total_allocated: string;
  total_outstanding: string;
  by_installment: InstallmentOutstanding[];
}

export interface Drift {
  student_id: string;
  installment_id: string;
  installment_number: number;
  cached_status: string;
  derived_status: string;
  invoiced: string;
  concessions: string;
  allocated: string;
  outstanding: string;
}

export interface InvariantViolation {
  kind: string;
  entity_id: string;
  detail: string;
}

export interface IntegrityReport {
  ok: boolean;
  checked_at: string; // ISO datetime
  students_checked: number;
  installments_checked: number;
  payments_checked: number;
  drifts: Drift[];
  invariant_violations: InvariantViolation[];
}

export interface AuditLog {
  id: string;
  actor_user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  ts: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface AuditPage {
  items: AuditLog[];
  limit: number;
  offset: number;
}
