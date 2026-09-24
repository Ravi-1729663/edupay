"use client";

import * as React from "react";
import { History, Search } from "lucide-react";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { PaymentStatusBadge } from "@/components/edupay/status-badge";
import {
  EmptyState,
  ErrorState,
  PaginationBar,
  TableSkeleton,
} from "@/components/edupay/ui-helpers";
import { useDebounced } from "@/components/edupay/use-async";
import {
  ApiError,
  apiFetch,
  type Page,
  type Payment,
  type Role,
} from "@/lib/api";
import { formatDateTime, formatMoney, truncateId } from "@/lib/money";

const PAGE_SIZE = 20;
const STATUS_OPTIONS = [
  "CREATED",
  "PENDING",
  "SUCCESS",
  "FAILED",
  "UNKNOWN",
  "REVERSAL_REQUESTED",
  "REVERSED",
] as const;

interface PaymentHistoryProps {
  role: Role;
  studentId?: string | null;
  onOpenPayment?: (paymentId: string) => void;
}

/**
 * Paginated payment list with filters (status dropdown + student search
 * for staff+ roles). Row click → Payment Details modal.
 *
 * When `role==="STUDENT"` and `studentId` is supplied, the list is scoped
 * to that student via `?student_id=` and the search box is hidden.
 */
export function PaymentHistory({ role, studentId, onOpenPayment }: PaymentHistoryProps) {
  const [status, setStatus] = React.useState<string>("ALL");
  const [q, setQ] = React.useState("");
  const debouncedQ = useDebounced(q.trim(), 350);
  const [offset, setOffset] = React.useState(0);
  const [data, setData] = React.useState<Page<Payment> | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<ApiError | null>(null);
  const [seq, setSeq] = React.useState(0);

  // Reset offset on filter change.
  React.useEffect(() => setOffset(0), [status, debouncedQ, studentId]);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    if (status !== "ALL") params.set("status", status);
    if (studentId) params.set("student_id", studentId);
    // q searches by student id on the backend (no text-search on payments
    // per the API). For a STAFF role without a studentId we still let
    // them paste a student_id or payment_id.
    if (debouncedQ && !studentId) params.set("student_id", debouncedQ);
    apiFetch<Page<Payment>>(`/payments?${params.toString()}`)
      .then((p) => {
        if (!cancelled) setData(p);
      })
      .catch((e) => {
        if (cancelled) return;
        const ae =
          e instanceof ApiError ? e : new ApiError(0, "error", "request failed");
        setError(ae);
        toast.error("Failed to load payments", { description: ae.message });
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [status, debouncedQ, offset, studentId, seq]);

  const isScoped = role === "STUDENT" && !!studentId;

  return (
    <Card className="border-slate-200">
      <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg">
            <History className="size-5 text-emerald-700" />
            {isScoped ? "My payments" : "Payments"}
          </CardTitle>
          <CardDescription>
            {isScoped
              ? "Your payment history. Click a row for full details."
              : "All payments. Click a row to drill into allocations + reversals."}
          </CardDescription>
        </div>
        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
          {!isScoped ? (
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <Input
                placeholder="Filter by student_id…"
                className="pl-8"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </div>
          ) : null}
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-full sm:w-40" size="sm">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All statuses</SelectItem>
              {STATUS_OPTIONS.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <ErrorState error={error} />
        ) : (
          <>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Student</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead>Method</TableHead>
                    <TableHead>Gateway ref</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableSkeleton rows={6} cols={7} />
                  ) : data && data.items.length > 0 ? (
                    data.items.map((p) => (
                      <TableRow
                        key={p.id}
                        className={
                          onOpenPayment
                            ? "cursor-pointer hover:bg-slate-50"
                            : ""
                        }
                        onClick={() => onOpenPayment?.(p.id)}
                      >
                        <TableCell className="font-mono text-[11px] text-slate-600">
                          {truncateId(p.id, 8)}
                        </TableCell>
                        <TableCell className="font-mono text-[11px] text-slate-600">
                          {truncateId(p.student_id, 8)}
                        </TableCell>
                        <TableCell className="text-right font-medium">
                          {formatMoney(p.amount)}
                        </TableCell>
                        <TableCell className="text-xs">{p.method}</TableCell>
                        <TableCell className="font-mono text-[11px] text-slate-500">
                          {p.gateway_ref ? truncateId(p.gateway_ref, 10) : "—"}
                        </TableCell>
                        <TableCell>
                          <PaymentStatusBadge status={p.status} />
                        </TableCell>
                        <TableCell className="font-mono text-[11px] text-slate-500">
                          {formatDateTime(p.created_at)}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={7} className="py-0 px-0 border-0">
                        <EmptyState
                          title="No payments match these filters"
                          message="Try clearing the status filter or the search box."
                        />
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
            {loading && !data ? <Skeleton className="h-1 w-full" /> : null}
            <PaginationBar
              offset={offset}
              pageSize={PAGE_SIZE}
              total={data?.total ?? 0}
              loading={loading}
              onPrev={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              onNext={() => setOffset(offset + PAGE_SIZE)}
            />
            <div className="text-[11px] text-slate-500 flex justify-between">
              <span>
                <button
                  type="button"
                  onClick={() => setSeq((n) => n + 1)}
                  className="hover:underline text-emerald-700"
                >
                  ↻ refresh
                </button>
              </span>
              <span>limit={PAGE_SIZE} · offset={offset}</span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
