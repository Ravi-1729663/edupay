"use client";

import * as React from "react";
import { AlertTriangle, User } from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/edupay/status-badge";
import { History } from "lucide-react";
import {
  ApiError,
  apiFetch,
  type Student,
  type StudentOutstanding,
} from "@/lib/api";
import { formatDate, formatMoney, truncateId } from "@/lib/money";

interface StudentFeeAccountModalProps {
  studentId: string | null;
  onClose: () => void;
  onOpenPayment?: (paymentId: string) => void;
}

/**
 * Modal showing /students/{id}/outstanding for a given student:
 *  - header (name, roll, program, batch)
 *  - by_installment breakdown with cached_status vs derived_status (amber
 *    drift highlight) + amount / concessions / allocated / outstanding
 *  - total outstanding big number
 */
export function StudentFeeAccountModal({
  studentId,
  onClose,
  onOpenPayment,
}: StudentFeeAccountModalProps) {
  const open = !!studentId;
  const [student, setStudent] = React.useState<Student | null>(null);
  const [out, setOut] = React.useState<StudentOutstanding | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<ApiError | null>(null);

  // Mini payment list (optional convenience link).
  const [seq, setSeq] = React.useState(0);

  React.useEffect(() => {
    if (!studentId) {
      setStudent(null);
      setOut(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setStudent(null);
    setOut(null);
    Promise.all([
      apiFetch<Student>(`/students/${studentId}`),
      apiFetch<StudentOutstanding>(`/students/${studentId}/outstanding`),
    ])
      .then(([s, o]) => {
        if (cancelled) return;
        setStudent(s);
        setOut(o);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(
          e instanceof ApiError ? e : new ApiError(0, "error", String(e)),
        );
        toast.error("Failed to load student account", {
          description: e instanceof ApiError ? e.message : String(e),
        });
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [studentId, seq]);

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
    >
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <User className="size-5 text-emerald-700" />
            Student fee account
            {student ? (
              <span className="font-mono text-xs text-slate-500 ml-1">
                {truncateId(student.id, 8)}
              </span>
            ) : null}
          </DialogTitle>
          <DialogDescription>
            Derived outstanding per installment — <code>cached_status</code>{" "}
            vs <code>derived_status</code>.
          </DialogDescription>
        </DialogHeader>

        {error ? (
          <Alert variant="destructive">
            <AlertTriangle className="size-4" />
            <AlertTitle>
              {error.code} (HTTP {error.status || "?"})
            </AlertTitle>
            <AlertDescription>
              {error.message}
              {error.requestId ? (
                <p className="font-mono text-[11px] opacity-80 mt-0.5">
                  request_id: {error.requestId}
                </p>
              ) : null}
            </AlertDescription>
          </Alert>
        ) : null}

        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : null}

        {student && out ? (
          <div className="space-y-4">
            {/* Header */}
            <div className="rounded-lg border border-slate-200 p-3 bg-slate-50/50 grid grid-cols-2 sm:grid-cols-4 gap-3">
              <Field label="Name" value={student.full_name} strong />
              <Field label="Roll" value={student.roll_number} mono />
              <Field label="Program" value={truncateId(student.program_id, 8)} mono />
              <Field label="Batch" value={String(student.batch_year)} mono />
              <Field label="Status" value={<StatusBadge status={student.status} />} />
              <Field label="Total invoiced" value={formatMoney(out.total_invoiced)} mono />
              <Field label="Concessions" value={formatMoney(out.total_concessions)} mono />
              <Field label="Allocated" value={formatMoney(out.total_allocated)} mono />
            </div>

            {/* Outstanding big number */}
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 flex items-center justify-between">
              <div>
                <div className="text-[11px] uppercase tracking-wide text-emerald-700">
                  Total outstanding
                </div>
                <div className="text-2xl font-bold text-emerald-800">
                  {formatMoney(out.total_outstanding)}
                </div>
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setSeq((n) => n + 1)}
                className="border-emerald-400 text-emerald-700 hover:bg-emerald-100"
              >
                ↻ Refresh
              </Button>
            </div>

            {/* Installment breakdown */}
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>Due</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="text-right">Concessions</TableHead>
                    <TableHead className="text-right">Allocated</TableHead>
                    <TableHead className="text-right">Outstanding</TableHead>
                    <TableHead>Cached</TableHead>
                    <TableHead>Derived</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {out.by_installment.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center text-slate-500 text-sm py-4">
                        No installments assigned.
                      </TableCell>
                    </TableRow>
                  ) : (
                    out.by_installment.map((i) => (
                      <TableRow
                        key={i.installment_id}
                        className={i.drift ? "bg-amber-50" : ""}
                      >
                        <TableCell>#{i.installment_number}</TableCell>
                        <TableCell className="font-mono text-xs">
                          {formatDate(i.due_date)}
                        </TableCell>
                        <TableCell className="text-right">
                          {formatMoney(i.amount)}
                        </TableCell>
                        <TableCell className="text-right text-slate-600">
                          {formatMoney(i.concessions)}
                        </TableCell>
                        <TableCell className="text-right text-slate-600">
                          {formatMoney(i.allocated)}
                        </TableCell>
                        <TableCell className="text-right font-medium">
                          {formatMoney(i.outstanding)}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={i.cached_status} />
                        </TableCell>
                        <TableCell>
                          {i.drift ? (
                            <span className="inline-flex items-center gap-1.5">
                              <StatusBadge status={i.derived_status} />
                              <span className="text-amber-700 text-[10px] font-medium uppercase">
                                drift
                              </span>
                            </span>
                          ) : (
                            <StatusBadge status={i.derived_status} />
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>

            {/* Action: open payment history (scoped to this student) */}
            {onOpenPayment ? (
              <div className="flex justify-end">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="border-slate-300"
                  onClick={() => {
                    // We can't directly open a specific payment here
                    // without knowing its id; instead the parent will
                    // switch to the Payment History tab scoped to this
                    // student. (Wire-up is done in dashboard.tsx.)
                    onOpenPayment?.(student.id);
                  }}
                >
                  <History className="size-4" />
                  View this student&apos;s payments
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function Field({
  label,
  value,
  strong,
  mono,
}: {
  label: string;
  value: React.ReactNode;
  strong?: boolean;
  mono?: boolean;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div
        className={
          "text-xs mt-0.5 " +
          (strong ? "font-semibold text-slate-900 " : "") +
          (mono ? "font-mono text-slate-700 " : "")
        }
      >
        {value}
      </div>
    </div>
  );
}
