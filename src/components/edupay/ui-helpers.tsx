"use client";

import * as React from "react";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import type { ApiError } from "@/lib/api";

/** Standard red error Alert showing the code + message + request_id. */
export function ErrorState({ error }: { error: ApiError | Error | string }) {
  const ae: ApiError =
    typeof error === "string"
      ? new (class extends ApiError {})(0, "error", error)
      : error instanceof ApiError
        ? error
        : new (class extends ApiError {})(0, "error", error.message);
  return (
    <Alert variant="destructive">
      <AlertTriangle className="size-4" />
      <AlertTitle>
        {ae.code || "error"}
        {ae.status ? ` (HTTP ${ae.status})` : ""}
      </AlertTitle>
      <AlertDescription>
        <p>{ae.message}</p>
        {ae.requestId ? (
          <p className="font-mono text-[11px] opacity-80 mt-0.5">
            request_id: {ae.requestId}
          </p>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}

/** Friendly empty state: icon + message. */
export function EmptyState({
  title = "Nothing to show here yet",
  message,
  icon,
}: {
  title?: string;
  message?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50/60 px-4 py-10 text-center">
      <div className="mx-auto size-10 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-400 mb-2">
        {icon ?? <Inbox className="size-5" />}
      </div>
      <p className="text-sm font-medium text-slate-700">{title}</p>
      {message ? (
        <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">{message}</p>
      ) : null}
    </div>
  );
}

/** Loading skeletons table. */
export function TableSkeleton({ rows = 6, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
      <span className="sr-only">Loading {rows}×{cols} table…</span>
    </div>
  );
}

export function InlineLoading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-8 text-sm text-slate-500">
      <Loader2 className="size-4 animate-spin" />
      {label}
    </div>
  );
}

interface PaginationBarProps {
  offset: number;
  pageSize: number;
  total: number;
  loading?: boolean;
  onPrev: () => void;
  onNext: () => void;
  /**
   * Override for "can we go next". If the backend omits `total` (e.g.
   * /admin/audit-logs), pass `hasNext` based on `items.length === pageSize`.
   * When provided, this wins over the total-based calculation.
   */
  hasNext?: boolean;
  /** Item count for the current page (used when total is unknown). */
  pageItems?: number;
}

/** "Showing X–Y of Z" + Previous/Next. */
export function PaginationBar({
  offset,
  pageSize,
  total,
  loading,
  onPrev,
  onNext,
  hasNext,
  pageItems,
}: PaginationBarProps) {
  const pageLen = pageItems ?? 0;
  const knownTotal = total > 0;
  const from = knownTotal ? Math.min(total, offset + 1) : pageLen > 0 ? offset + 1 : 0;
  const to = knownTotal
    ? Math.min(total, offset + pageSize)
    : offset + pageLen;
  const canPrev = offset > 0;
  // If caller passed hasNext explicitly, trust it; otherwise derive from total.
  const canNext =
    hasNext ?? (knownTotal ? to < total : pageLen >= pageSize);

  const summary = knownTotal
    ? total === 0
      ? "0 records"
      : `Showing ${from}–${to} of ${total}`
    : pageLen > 0
      ? `Showing ${from}–${to}`
      : "0 records on this page";

  return (
    <div className="flex items-center justify-between text-xs text-slate-600">
      <span>{summary}</span>
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={!canPrev || loading}
          onClick={onPrev}
        >
          Previous
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={!canNext || loading}
          onClick={onNext}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

/** Generic alert-and-retry banner for a failed fetch. */
export function RetryBanner({
  error,
  onRetry,
  loading,
}: {
  error: ApiError | Error | string;
  onRetry: () => void;
  loading?: boolean;
}) {
  return (
    <div className="space-y-2">
      <ErrorState error={error} />
      <Button
        size="sm"
        variant="outline"
        onClick={onRetry}
        disabled={loading}
        className="border-slate-300"
      >
        {loading ? <Loader2 className="size-4 animate-spin" /> : null}
        Retry
      </Button>
    </div>
  );
}

/** Format a status enum value for a Select box. */
export function statusOptions(values: readonly string[]) {
  return values.map((v) => ({ label: v, value: v }));
}
