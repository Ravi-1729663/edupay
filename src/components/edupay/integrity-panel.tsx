"use client";

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/edupay/status-badge";
import {
  ApiError,
  apiFetch,
  type IntegrityReport,
} from "@/lib/api";
import { formatDateTime, formatMoney } from "@/lib/money";

/**
 * The integrity checker is THE differentiator of Package A — derived
 * outstanding vs cached status across the whole DB. Make this look
 * trustworthy and unmissable.
 */
export function IntegrityPanel() {
  const [report, setReport] = React.useState<IntegrityReport | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<ApiError | null>(null);

  const run = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch<IntegrityReport>("/admin/integrity-check");
      setReport(r);
      if (r.ok) {
        toast.success("Integrity check passed", {
          description: `${r.students_checked} students · ${r.installments_checked} installments · ${r.payments_checked} payments`,
        });
      } else {
        toast.warning(`Integrity drift detected`, {
          description: `${r.drifts.length} drifts · ${r.invariant_violations.length} invariant violations`,
        });
      }
    } catch (e) {
      const ae = e instanceof ApiError ? e : new ApiError(0, "error", "request failed");
      setError(ae);
      toast.error("Integrity check failed", { description: ae.message });
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <Card className="border-slate-200">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2 text-lg">
            <ShieldCheck className="size-5 text-emerald-700" />
            Data integrity check
          </CardTitle>
          <CardDescription>
            Verifies every installment&apos;s cached <code>status</code> against
            the derived outstanding (invoiced − concessions − allocations) and
            scans cross-row invariants (allocation ≤ payment, reversal ≤ original).
          </CardDescription>
        </div>
        <Button
          type="button"
          onClick={run}
          disabled={loading}
          variant="outline"
          className="border-emerald-600 text-emerald-700 hover:bg-emerald-50"
        >
          {loading ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <RefreshCw className="size-4" />
          )}
          Run integrity check
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <Alert variant="destructive">
            <AlertTriangle className="size-4" />
            <AlertTitle>{error.code} (HTTP {error.status || "?"})</AlertTitle>
            <AlertDescription>
              <p>{error.message}</p>
              {error.requestId ? (
                <p className="font-mono text-[11px] opacity-80">
                  request_id: {error.requestId}
                </p>
              ) : null}
            </AlertDescription>
          </Alert>
        ) : null}

        {!report && !loading && !error ? (
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50/60 p-6 text-center text-sm text-slate-600">
            Press <span className="font-semibold">Run integrity check</span> to
            verify the ledger.
          </div>
        ) : null}

        {loading && !report ? (
          <div className="space-y-3">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : null}

        {report ? (
          <>
            <div
              className={
                "rounded-lg border p-4 " +
                (report.ok
                  ? "border-emerald-300 bg-emerald-50"
                  : "border-red-300 bg-red-50")
              }
            >
              <div className="flex items-start gap-3">
                {report.ok ? (
                  <CheckCircle2 className="size-6 text-emerald-700 shrink-0" />
                ) : (
                  <AlertTriangle className="size-6 text-red-700 shrink-0" />
                )}
                <div className="space-y-1">
                  <p className="font-semibold text-base">
                    {report.ok
                      ? "All ledgers consistent"
                      : "Drift / invariant violations detected"}
                  </p>
                  <p className="text-xs text-slate-700">
                    Checked at {formatDateTime(report.checked_at)}
                  </p>
                </div>
              </div>
              <dl className="mt-3 grid grid-cols-3 gap-3 text-center">
                <Stat label="Students" value={report.students_checked} />
                <Stat label="Installments" value={report.installments_checked} />
                <Stat label="Payments" value={report.payments_checked} />
              </dl>
            </div>

            {report.drifts.length > 0 ? (
              <div>
                <h4 className="text-sm font-semibold text-red-700 mb-2">
                  Status drifts ({report.drifts.length})
                </h4>
                <div className="overflow-x-auto rounded-lg border border-red-200">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Student</TableHead>
                        <TableHead>Inst #</TableHead>
                        <TableHead className="text-right">Invoiced</TableHead>
                        <TableHead className="text-right">Allocated</TableHead>
                        <TableHead className="text-right">Outstanding</TableHead>
                        <TableHead>Cached</TableHead>
                        <TableHead>Derived</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {report.drifts.map((d) => (
                        <TableRow key={d.installment_id + d.student_id}>
                          <TableCell className="font-mono text-[11px] text-slate-600">
                            {d.student_id.slice(0, 8)}…
                          </TableCell>
                          <TableCell>#{d.installment_number}</TableCell>
                          <TableCell className="text-right">
                            {formatMoney(d.invoiced)}
                          </TableCell>
                          <TableCell className="text-right">
                            {formatMoney(d.allocated)}
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            {formatMoney(d.outstanding)}
                          </TableCell>
                          <TableCell>
                            <StatusBadge status={d.cached_status} />
                          </TableCell>
                          <TableCell>
                            <StatusBadge status={d.derived_status} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            ) : null}

            {report.invariant_violations.length > 0 ? (
              <div>
                <h4 className="text-sm font-semibold text-red-700 mb-2">
                  Invariant violations ({report.invariant_violations.length})
                </h4>
                <div className="overflow-x-auto rounded-lg border border-red-200">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Kind</TableHead>
                        <TableHead>Entity</TableHead>
                        <TableHead>Detail</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {report.invariant_violations.map((v, i) => (
                        <TableRow key={v.entity_id + i}>
                          <TableCell className="font-mono text-[11px]">
                            {v.kind}
                          </TableCell>
                          <TableCell className="font-mono text-[11px] text-slate-600">
                            {v.entity_id.slice(0, 8)}…
                          </TableCell>
                          <TableCell className="text-xs">{v.detail}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            ) : null}

            {report.ok ? (
              <p className="text-xs text-slate-600">
                No drifts and no invariant violations. The ledger is internally
                consistent.
              </p>
            ) : null}
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-white/70 border border-slate-200 px-2 py-2">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className="text-lg font-semibold text-slate-900">{value}</div>
    </div>
  );
}
