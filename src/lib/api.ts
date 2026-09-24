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
  const callerHeaders: Record<string, string> =
    (init?.headers as Record<string, string>) ?? {};
  const headers: Record<string, string> = { ...callerHeaders };
  // Only set Content-Type=application/json if caller didn't supply one and
  // the body isn't a FormData (which needs the browser to set the multipart
  // boundary).
  const hasContentType = Object.keys(headers).some(
    (k) => k.toLowerCase() === "content-type",
  );
  const isFormData =
    typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (!hasContentType && !isFormData) {
    headers["Content-Type"] = "application/json";
  }
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
  total?: number;
  limit: number;
  offset: number;
}

// ── Catalog (departments / programs / fee heads / fee structures) ──

export interface Department {
  id: string;
  code: string;
  name: string;
}

export interface Program {
  id: string;
  code: string;
  name: string;
  department_id: string;
  duration_years: number;
}

export interface FeeHead {
  id: string;
  code: string;
  name: string;
  description?: string | null;
  priority: number;
  is_refundable: boolean;
}

export interface FeeStructureLine {
  id: string;
  fee_head_id: string;
  amount: string;
}

export interface FeeStructure {
  id: string;
  program_id: string;
  academic_year: string;
  effective_from: string | null;
  effective_to: string | null;
  is_active: boolean;
  lines: FeeStructureLine[];
}

// ── Payments ────────────────────────────────────────────────────────

export type PaymentStatus =
  | "CREATED"
  | "PENDING"
  | "SUCCESS"
  | "FAILED"
  | "UNKNOWN"
  | "REVERSAL_REQUESTED"
  | "REVERSED";

export type PaymentMethod = "CASH" | "CHEQUE" | "ONLINE";

export interface Payment {
  id: string;
  student_id: string;
  payer_user_id?: string | null;
  amount: string;
  method: PaymentMethod;
  gateway_ref?: string | null;
  status: PaymentStatus;
  idempotency_key?: string | null;
  initiated_by?: string | null;
  callback_received_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Allocation {
  id: string;
  payment_id: string;
  installment_id: string;
  fee_head_id: string;
  amount: string;
  created_at?: string;
}

export type ReversalStatus = "REQUESTED" | "COMPLETED";

export interface Reversal {
  id: string;
  original_payment_id: string;
  amount: string;
  reason: string;
  status: ReversalStatus;
  requested_by?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface PaymentDetail {
  payment: Payment;
  allocations: Allocation[];
  reversals: Reversal[];
}

export interface PaymentPage {
  items: Payment[];
  total: number;
  limit: number;
  offset: number;
}

export interface PaymentVerifyResponse {
  payment_id: string;
  status: PaymentStatus;
  message?: string | null;
}

export interface PaymentInitiateResponse {
  payment_id: string;
  gateway_ref: string;
  redirect_url: string;
  status: PaymentStatus;
}

export interface PaymentCounterResponse {
  payment: Payment;
  allocations: Allocation[];
  reversals: Reversal[];
}

// ── Reconciliation ──────────────────────────────────────────────────

export type ReconClassification =
  | "MATCHED"
  | "AMOUNT_MISMATCH"
  | "MISSING_INTERNAL"
  | "MISSING_EXTERNAL"
  | "DUPLICATE";

export interface ReconBatch {
  id: string;
  uploaded_by?: string | null;
  source_file_name: string;
  total_lines: number;
  matched_count: number;
  amount_mismatch_count: number;
  missing_internal_count: number;
  missing_external_count: number;
  duplicate_count: number;
  created_at: string;
}

export interface ReconBatchPage {
  items: ReconBatch[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReconLine {
  id: string;
  batch_id: string;
  external_reference: string;
  external_amount: string;
  student_id?: string | null;
  payment_id?: string | null;
  classification: ReconClassification;
  suggested_payment_id?: string | null;
  notes?: string | null;
  resolved_classification?: ReconClassification | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
  resolution_notes?: string | null;
  created_at: string;
}

export interface ReconLinePage {
  items: ReconLine[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReconUploadResponse {
  batch: ReconBatch;
  lines: ReconLine[];
}

// ── Mock Gateway chaos ──────────────────────────────────────────────

export type ChaosMode =
  | "SUCCESS"
  | "FAILED"
  | "TIMEOUT_NO_CALLBACK"
  | "DUPLICATE_CALLBACK"
  | "LATE_CALLBACK";

export interface ChaosSetting {
  mode: ChaosMode;
  delay_seconds: number;
}
