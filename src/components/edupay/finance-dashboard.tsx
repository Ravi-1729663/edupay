"use client";

import * as React from "react";
import {
  Banknote,
  Clock,
  Database,
  History,
  RotateCcw,
  TrendingUp,
  XCircle,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { CssBarChart, KpiCard } from "@/components/edupay/css-bar";
import { ErrorState, InlineLoading } from "@/components/edupay/ui-helpers";
import {
  ApiError,
  apiFetch,
  type Payment,
  type PaymentPage,
} from "@/lib/api";
import { formatDateTime, formatMoney, toNumber, truncateId } from "@/lib/money";

interface FinanceDashboardProps {
  onOpenPayment?: (paymentId: string) => void;
}

/**
 * Package D Finance Dashboard. Pure-CSS bar charts (no charting library).
 *
 * The backend's `/reports/*` summary endpoints are Package D-doc, so we
 * compute the KPIs client-side by pulling `/payments?status=<S>&limit=200`
 * for each status bucket + a `/payments?limit=10` for recent.
 */
export function FinanceDashboard({ onOpenPayment }: FinanceDashboardProps) {
  // Each status bucket is fetched in parallel — the backend's
  // /payments endpoint filters by `status` query param.
  const [buckets, setBuckets] = React.useState<Record<string, Payment[]>>({});
  const [recent, setRecent] = React.useState<Payment[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<ApiError | null>(null);
  const [reloadSeq, setReloadSeq] = React.useState(0);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const statuses = ["SUCCESS", "FAILED", "PENDING", "UNKNOWN", "REVERSED", "REVERSAL_REQUESTED"];
    Promise.all(
      statuses.map((s) =>
        apiFetch<PaymentPage>(
          `/payments?status=${encodeURIComponent(s)}&limit=200&offset=0`,
        )
          .then((p) => [s, p.items] as const)
          .catch((e) => {
            // Don't fail the whole dashboard if one bucket 403s.
            if (e instanceof ApiError && e.status === 403) return [s, []] as const;
            throw e;
          }),
      ),
    )
      .then(async (entries) => {
        const map: Record<string, Payment[]> = {};
        for (const [s, items] of entries) map[s] = items;
        // Recent: fetch separately (no status filter).
        const r = await apiFetch<PaymentPage>("/payments?limit=10&offset=0");
        if (cancelled) return;
        setBuckets(map);
        setRecent(r.items);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof ApiError ? e : new ApiError(0, "error", String(e)));
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [reloadSeq]);

  const success = buckets["SUCCESS"] ?? [];
  const failed = buckets["FAILED"] ?? [];
  const pending = buckets["PENDING"] ?? [];
  const unknown = buckets["UNKNOWN"] ?? [];
  const reversalRequested = buckets["REVERSAL_REQUESTED"] ?? [];
  const reversed = buckets["REVERSED"] ?? [];

  const collectedSum = success.reduce((a, p) => a + toNumber(p.amount), 0);
  const failedCount = failed.length;
  const pendingCount = pending.length + unknown.length;
  const reversedCount = reversed.length + reversalRequested.length;

  // By-status CSS bar (computed from counts).
  const statusBars = [
    {
      label: "Success",
      value: success.length,
      colorClass: "bg-emerald-500",
      display: String(success.length),
    },
    {
      label: "Pending",
      value: pending.length,
      colorClass: "bg-amber-500",
      display: String(pending.length),
    },
    {
      label: "Unknown",
      value: unknown.length,
      colorClass: "bg-amber-400",
      display: String(unknown.length),
    },
    {
      label: "Failed",
      value: failed.length,
      colorClass: "bg-rose-500",
      display: String(failed.length),
    },
    {
      label: "Reversal req'd",
      value: reversalRequested.length,
      colorClass: "bg-amber-600",
      display: String(reversalRequested.length),
    },
    {
      label: "Reversed",
      value: reversed.length,
      colorClass: "bg-slate-500",
      display: String(reversed.length),
    },
  ];

  // By-method collected CSS bar (only successful payments contribute).
  const byMethod = (["CASH", "CHEQUE", "ONLINE"] as const).map((m) => {
    const sum = success
      .filter((p) => p.method === m)
      .reduce((a, p) => a + toNumber(p.amount), 0);
    return {
      label: m,
      value: sum,
      display: formatMoney(String(sum)),
    };
  });

  const totalCollected = byMethod.reduce((a, d) => a + d.value, 0);

  return (
    <Card className="border-slate-200">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2 text-lg">
            <TrendingUp className="size-5 text-emerald-700" />
            Finance dashboard
          </CardTitle>
          <CardDescription>
            Live collections view. Pulled client-side from{" "}
            <code className="font-mono text-[11px]">/payments?status=…</code>{" "}
            buckets — Package D-doc <code className="font-mono text-[11px]">/reports/*</code>{" "}
            endpoints would aggregate these server-side.
          </CardDescription>
        </div>
        <button
          type="button"
          onClick={() => setReloadSeq((n) => n + 1)}
          className="text-xs text-emerald-700 hover:underline"
        >
          ↻ Refresh
        </button>
      </CardHeader>
      <CardContent className="space-y-5">
        {error ? (
          <ErrorState error={error} />
        ) : loading ? (
          <InlineLoading label="Aggregating payments…" />
        ) : (
          <>
            {/* KPI cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <KpiCard
                label="Collected"
                value={formatMoney(String(collectedSum))}
                sub={`${success.length} successful payment${success.length === 1 ? "" : "s"}`}
                tone="emerald"
                icon={<Banknote className="size-4" />}
              />
              <KpiCard
                label="Failed"
                value={String(failedCount)}
                sub="returned by gateway"
                tone="rose"
                icon={<XCircle className="size-4" />}
              />
              <KpiCard
                label="Pending / Unknown"
                value={String(pendingCount)}
                sub="awaiting callback or verify"
                tone="amber"
                icon={<Clock className="size-4" />}
              />
              <KpiCard
                label="Reversed"
                value={String(reversedCount)}
                sub="incl. reversal requests"
                tone="slate"
                icon={<RotateCcw className="size-4" />}
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* By-status bar chart */}
              <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Database className="size-4 text-slate-500" />
                  <h4 className="text-sm font-semibold text-slate-800">
                    Payments by status
                  </h4>
                </div>
                <CssBarChart
                  data={statusBars}
                  total={Math.max(
                    1,
                    ...statusBars.map((b) => b.value),
                  )}
                  emptyLabel="No payments on file."
                />
              </div>

              {/* By-method bar chart */}
              <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Banknote className="size-4 text-slate-500" />
                  <h4 className="text-sm font-semibold text-slate-800">
                    Collected by method
                  </h4>
                  <span className="text-xs text-slate-500 ml-auto">
                    Σ {formatMoney(String(totalCollected))}
                  </span>
                </div>
                <CssBarChart
                  data={byMethod}
                  total={totalCollected}
                  emptyLabel="No successful collections yet."
                />
              </div>
            </div>

            {/* Recent payments */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <History className="size-4 text-slate-500" />
                <h4 className="text-sm font-semibold text-slate-800">
                  Recent payments
                </h4>
                <span className="text-xs text-slate-500">last 10</span>
              </div>
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>ID</TableHead>
                      <TableHead>Student</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      <TableHead>Method</TableHead>
                      <TableHead>Gateway</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>When</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {recent.length === 0 ? (
                      <TableRow>
                        <TableCell
                          colSpan={7}
                          className="text-center text-slate-500 text-sm py-6"
                        >
                          No payments yet.
                        </TableCell>
                      </TableRow>
                    ) : (
                      recent.map((p) => (
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
                    )}
                  </TableBody>
                </Table>
              </div>
            </div>
          </>
        )}
        {loading && (
          <div className="space-y-3">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
