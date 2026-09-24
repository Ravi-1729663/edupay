"use client";

import * as React from "react";
import { AlertTriangle, CreditCard, Loader2, Wallet } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/edupay/status-badge";
import { ChaosPanel } from "@/components/edupay/chaos-panel";
import {
  ApiError,
  apiFetch,
  type StudentOutstanding,
} from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/money";

/**
 * STUDENT role view: shows the student their own outstanding, with an
 * amber alert if any installment is OVERDUE. Includes the Package B
 * placeholders for payment initiation and the chaos panel.
 */
export function StudentFees({ studentId }: { studentId: string }) {
  const [data, setData] = React.useState<StudentOutstanding | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<ApiError | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiFetch<StudentOutstanding>(`/students/${studentId}/outstanding`)
      .then((d) => !cancelled && setData(d))
      .catch((e) => {
        if (cancelled) return;
        const ae = e instanceof ApiError ? e : new ApiError(0, "error", "request failed");
        setError(ae);
        toast.error("Failed to load fees", { description: ae.message });
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [studentId]);

  const overdue = data?.by_installment.filter(
    (i) => i.derived_status === "OVERDUE",
  ) ?? [];
  const totalOutstanding = data ? formatMoney(data.total_outstanding) : "—";

  return (
    <div className="space-y-4">
      <Card className="border-slate-200">
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Wallet className="size-5 text-emerald-700" />
              My fees
            </CardTitle>
            <CardDescription>
              Your current outstanding, derived live from the ledger.
            </CardDescription>
          </div>
          <div className="text-right">
            <div className="text-[11px] uppercase tracking-wide text-slate-500">
              Outstanding
            </div>
            <div className="text-2xl font-semibold text-emerald-700">
              {totalOutstanding}
            </div>
          </div>
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

          {overdue.length > 0 ? (
            <Alert className="border-amber-300 bg-amber-50 text-amber-900">
              <AlertTriangle className="size-4 text-amber-700" />
              <AlertTitle className="text-amber-900">
                {overdue.length} overdue installment{overdue.length > 1 ? "s" : ""}
              </AlertTitle>
              <AlertDescription className="text-amber-800">
                Please clear overdue amounts to avoid late-fee accrual. Payment
                initiation will be available in Package B.
              </AlertDescription>
            </Alert>
          ) : null}

          {loading ? (
            <Skeleton className="h-40 w-full" />
          ) : data ? (
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>Due</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="text-right">Paid</TableHead>
                    <TableHead className="text-right">Outstanding</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.by_installment.map((i) => (
                    <TableRow key={i.installment_id}>
                      <TableCell>#{i.installment_number}</TableCell>
                      <TableCell className="font-mono text-xs">
                        {formatDate(i.due_date)}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatMoney(i.amount)}
                      </TableCell>
                      <TableCell className="text-right text-slate-600">
                        {formatMoney(i.allocated)}
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {formatMoney(i.outstanding)}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={i.derived_status} />
                      </TableCell>
                    </TableRow>
                  ))}
                  {data.by_installment.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-slate-500 text-sm py-6">
                        No installments on file.
                      </TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </div>
          ) : null}

          {data && data.by_installment.length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <MiniStat label="Total invoiced" value={formatMoney(data.total_invoiced)} />
              <MiniStat label="Concessions" value={formatMoney(data.total_concessions)} />
              <MiniStat label="Allocated" value={formatMoney(data.total_allocated)} />
              <MiniStat label="Outstanding" value={formatMoney(data.total_outstanding)} tone="emerald" />
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card className="border-dashed border-slate-300 bg-slate-50/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <CreditCard className="size-5 text-slate-600" />
            Payments
            <span className="text-[11px] font-medium text-slate-500">
              · Package B
            </span>
          </CardTitle>
          <CardDescription>
            Online payment initiation will be available in Package B.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button type="button" disabled className="bg-slate-600/70">
            {loading ? <Loader2 className="size-4 animate-spin" /> : null}
            Pay now (disabled)
          </Button>
        </CardContent>
        <CardFooter className="text-[11px] text-slate-500">
          Will call <code>POST /payments/initiate</code> through the MockGateway.
        </CardFooter>
      </Card>

      <ChaosPanel />
    </div>
  );
}

function MiniStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "emerald";
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-2.5 py-2">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div
        className={
          "text-sm font-semibold " +
          (tone === "emerald" ? "text-emerald-700" : "text-slate-900")
        }
      >
        {value}
      </div>
    </div>
  );
}
