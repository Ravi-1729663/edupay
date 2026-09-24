"use client";

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CreditCard,
  Info,
  RotateCcw,
  ShieldQuestion,
} from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { PaymentStatusBadge } from "@/components/edupay/status-badge";
import { ConfirmDialog } from "@/components/edupay/confirm-dialog";
import {
  ApiError,
  apiFetch,
  type Allocation,
  type Payment,
  type PaymentDetail,
  type PaymentVerifyResponse,
  type Reversal,
  type Role,
} from "@/lib/api";
import { formatDateTime, formatMoney, truncateId } from "@/lib/money";

interface PaymentDetailsModalProps {
  paymentId: string | null;
  role: Role;
  onClose: () => void;
}

/**
 * Modal that shows GET /payments/{id}:
 *  - payment header (id, status, amount, method, gateway_ref, initiated_by,
 *    created_at, callback_received_at)
 *  - allocations table
 *  - reversals list
 *
 * Action buttons (role-aware):
 *  - status=UNKNOWN or PENDING → "Verify payment" (POST /payments/{id}/verify)
 *  - status=SUCCESS → "Request reversal" (MANAGER/ADMIN) → opens form +
 *    confirmation dialog → POST /payments/{id}/reversal-request
 *  - reversal in REQUESTED state → "Approve reversal" (MANAGER/ADMIN) →
 *    POST /payments/{id}/reversal-complete with confirmation
 *  - STUDENT → read-only
 */
export function PaymentDetailsModal({
  paymentId,
  role,
  onClose,
}: PaymentDetailsModalProps) {
  const open = !!paymentId;
  const [data, setData] = React.useState<PaymentDetail | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<ApiError | null>(null);
  const [seq, setSeq] = React.useState(0);

  // Reversal request form state.
  const [revAmount, setRevAmount] = React.useState("");
  const [revReason, setRevReason] = React.useState("");
  const [revDialogOpen, setRevDialogOpen] = React.useState(false);
  const [confirmRevOpen, setConfirmRevOpen] = React.useState(false);

  // Confirm dialogs for verify + reversal complete.
  const [verifyDialogOpen, setVerifyDialogOpen] = React.useState(false);
  const [approveDialogOpen, setApproveDialogOpen] = React.useState(false);

  // Loading flags for the action buttons.
  const [verifyLoading, setVerifyLoading] = React.useState(false);
  const [revReqLoading, setRevReqLoading] = React.useState(false);
  const [approveLoading, setApproveLoading] = React.useState(false);

  React.useEffect(() => {
    if (!paymentId) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    apiFetch<PaymentDetail>(`/payments/${paymentId}`)
      .then((d) => !cancelled && setData(d))
      .catch((e) => {
        if (cancelled) return;
        setError(
          e instanceof ApiError ? e : new ApiError(0, "error", String(e)),
        );
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [paymentId, seq]);

  // Reset form on close.
  React.useEffect(() => {
    if (!open) {
      setRevAmount("");
      setRevReason("");
      setRevDialogOpen(false);
      setConfirmRevOpen(false);
      setVerifyDialogOpen(false);
      setApproveDialogOpen(false);
    }
  }, [open]);

  const payment: Payment | null = data?.payment ?? null;
  const allocations: Allocation[] = data?.allocations ?? [];
  const reversals: Reversal[] = data?.reversals ?? [];

  // Pre-fill reversal amount with the payment amount on first load.
  React.useEffect(() => {
    if (payment && !revAmount) setRevAmount(String(payment.amount));
  }, [payment, revAmount]);

  const canVerify =
    !!payment &&
    (payment.status === "UNKNOWN" || payment.status === "PENDING");
  const canRequestReversal =
    !!payment &&
    payment.status === "SUCCESS" &&
    (role === "FINANCE_MANAGER" || role === "ADMIN");
  const pendingReversal = reversals.find((r) => r.status === "REQUESTED");
  const canApproveReversal =
    !!pendingReversal &&
    (role === "FINANCE_MANAGER" || role === "ADMIN");
  const isReversalPending = payment?.status === "REVERSAL_REQUESTED";

  async function doVerify() {
    if (!payment) return;
    setVerifyLoading(true);
    try {
      const r = await apiFetch<PaymentVerifyResponse>(
        `/payments/${payment.id}/verify`,
        { method: "POST" },
      );
      toast.success("Verify completed", {
        description: `Status is now ${r.status}${r.message ? " · " + r.message : ""}`,
      });
      setSeq((n) => n + 1);
    } catch (e) {
      const ae =
        e instanceof ApiError ? e : new ApiError(0, "error", String(e));
      toast.error("Verify failed", { description: ae.message });
      throw e;
    } finally {
      setVerifyLoading(false);
    }
  }

  async function doRequestReversal() {
    if (!payment) return;
    const body = {
      amount: revAmount,
      reason: revReason.trim(),
    };
    if (!body.reason) {
      toast.error("A reversal reason is required");
      throw new Error("reason required");
    }
    setRevReqLoading(true);
    try {
      await apiFetch(`/payments/${payment.id}/reversal-request`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      toast.success("Reversal requested", {
        description: "A finance manager must approve it.",
      });
      setRevDialogOpen(false);
      setConfirmRevOpen(false);
      setSeq((n) => n + 1);
    } catch (e) {
      const ae =
        e instanceof ApiError ? e : new ApiError(0, "error", String(e));
      toast.error("Reversal request failed", { description: ae.message });
      throw e;
    } finally {
      setRevReqLoading(false);
    }
  }

  async function doApproveReversal() {
    if (!payment) return;
    setApproveLoading(true);
    try {
      await apiFetch(`/payments/${payment.id}/reversal-complete`, {
        method: "POST",
      });
      toast.success("Reversal completed");
      setSeq((n) => n + 1);
    } catch (e) {
      const ae =
        e instanceof ApiError ? e : new ApiError(0, "error", String(e));
      toast.error("Approve reversal failed", { description: ae.message });
      throw e;
    } finally {
      setApproveLoading(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
    >
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <CreditCard className="size-5 text-emerald-700" />
            Payment details
            {payment ? (
              <span className="font-mono text-xs text-slate-500 ml-1">
                {truncateId(payment.id, 8)}
              </span>
            ) : null}
          </DialogTitle>
          <DialogDescription>Payment + allocations + reversals.</DialogDescription>
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
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        ) : null}

        {payment ? (
          <div className="space-y-4">
            {/* Header */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 rounded-lg border border-slate-200 p-3 bg-slate-50/50">
              <Detail label="Status" value={<PaymentStatusBadge status={payment.status} />} />
              <Detail label="Amount" value={<span className="font-semibold text-slate-900">{formatMoney(payment.amount)}</span>} />
              <Detail label="Method" value={<span className="font-mono text-xs">{payment.method}</span>} />
              <Detail label="Gateway ref" value={<span className="font-mono text-xs text-slate-600">{payment.gateway_ref ?? "—"}</span>} />
              <Detail label="Initiated by" value={<span className="font-mono text-[11px] text-slate-500">{payment.initiated_by ? truncateId(payment.initiated_by, 8) : "—"}</span>} />
              <Detail label="Created" value={<span className="font-mono text-[11px] text-slate-500">{formatDateTime(payment.created_at)}</span>} />
              <Detail label="Updated" value={<span className="font-mono text-[11px] text-slate-500">{formatDateTime(payment.updated_at)}</span>} />
              <Detail label="Callback at" value={<span className="font-mono text-[11px] text-slate-500">{payment.callback_received_at ? formatDateTime(payment.callback_received_at) : "—"}</span>} />
              <Detail label="Student" value={<span className="font-mono text-[11px] text-slate-500">{truncateId(payment.student_id, 8)}</span>} />
            </div>

            {/* Allocations */}
            <div>
              <h4 className="text-sm font-semibold text-slate-800 mb-1.5">
                Allocations ({allocations.length})
              </h4>
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Installment</TableHead>
                      <TableHead>Fee head</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {allocations.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={3} className="text-center text-slate-500 text-sm py-4">
                          No allocations — payment may be unallocated or reversed.
                        </TableCell>
                      </TableRow>
                    ) : (
                      allocations.map((a) => (
                        <TableRow key={a.id}>
                          <TableCell className="font-mono text-[11px] text-slate-600">
                            {truncateId(a.installment_id, 8)}
                          </TableCell>
                          <TableCell className="font-mono text-[11px] text-slate-600">
                            {truncateId(a.fee_head_id, 8)}
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            {formatMoney(a.amount)}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </div>

            {/* Reversals */}
            <div>
              <h4 className="text-sm font-semibold text-slate-800 mb-1.5">
                Reversals ({reversals.length})
              </h4>
              {reversals.length === 0 ? (
                <p className="text-xs text-slate-500">No reversals on this payment.</p>
              ) : (
                <div className="space-y-2">
                  {reversals.map((r) => (
                    <div
                      key={r.id}
                      className="rounded-md border border-slate-200 bg-white p-2.5 text-xs space-y-1"
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={
                            "inline-block rounded-md border px-1.5 py-0.5 font-mono text-[10px] " +
                            (r.status === "COMPLETED"
                              ? "border-slate-300 bg-slate-50 text-slate-600 line-through"
                              : "border-amber-300 bg-amber-50 text-amber-800")
                          }
                        >
                          {r.status}
                        </span>
                        <span className="font-semibold text-slate-800">
                          {formatMoney(r.amount)}
                        </span>
                        <span className="text-slate-500 ml-auto">
                          requested by {r.requested_by ? truncateId(r.requested_by, 8) : "—"}
                          {" · "}
                          {formatDateTime(r.created_at)}
                        </span>
                      </div>
                      <p className="text-slate-700">
                        <span className="font-medium">Reason:</span> {r.reason}
                      </p>
                      {r.resolution_notes ? (
                        <p className="text-slate-700">
                          <span className="font-medium">Notes:</span>{" "}
                          {r.resolution_notes}
                        </p>
                      ) : null}
                      {r.completed_at ? (
                        <p className="text-slate-500 text-[11px]">
                          Completed at {formatDateTime(r.completed_at)}
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Actions (role-aware) */}
            {role === "STUDENT" ? (
              <Alert>
                <Info className="size-4" />
                <AlertDescription>
                  You have read-only access to this payment. Contact the finance
                  office to request a reversal.
                </AlertDescription>
              </Alert>
            ) : (
              <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-200">
                {canVerify ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setVerifyDialogOpen(true)}
                    className="border-amber-400 text-amber-800 hover:bg-amber-50"
                  >
                    <ShieldQuestion className="size-4" />
                    Verify payment
                  </Button>
                ) : null}
                {canRequestReversal ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setRevDialogOpen(true)}
                    className="border-rose-400 text-rose-700 hover:bg-rose-50"
                  >
                    <RotateCcw className="size-4" />
                    Request reversal
                  </Button>
                ) : null}
                {isReversalPending || canApproveReversal ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setApproveDialogOpen(true)}
                    className="border-emerald-500 text-emerald-700 hover:bg-emerald-50"
                  >
                    <CheckCircle2 className="size-4" />
                    Approve reversal
                  </Button>
                ) : null}
                {!canVerify &&
                !canRequestReversal &&
                !isReversalPending &&
                !canApproveReversal ? (
                  <span className="text-xs text-slate-500 self-center">
                    No actions available for this payment state.
                  </span>
                ) : null}
              </div>
            )}

            {/* Reversal request inline form */}
            {revDialogOpen ? (
              <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <RotateCcw className="size-4 text-rose-700" />
                  <h4 className="text-sm font-semibold text-rose-900">
                    Request reversal
                  </h4>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <Label htmlFor="rev-amount" className="text-xs">
                      Amount
                    </Label>
                    <Input
                      id="rev-amount"
                      type="number"
                      step="0.01"
                      min="0"
                      value={revAmount}
                      onChange={(e) => setRevAmount(e.target.value)}
                      className="font-mono"
                    />
                  </div>
                  <div className="space-y-1 sm:col-span-2">
                    <Label htmlFor="rev-reason" className="text-xs">
                      Reason (required)
                    </Label>
                    <Textarea
                      id="rev-reason"
                      rows={2}
                      placeholder="Why is this payment being reversed?"
                      value={revReason}
                      onChange={(e) => setRevReason(e.target.value)}
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setRevDialogOpen(false)}
                    disabled={revReqLoading}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => {
                      if (!revReason.trim()) {
                        toast.error("A reversal reason is required");
                        return;
                      }
                      setConfirmRevOpen(true);
                    }}
                    className="bg-rose-600 text-white hover:bg-rose-700"
                  >
                    Next: confirm
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {/* Verify confirm */}
        <ConfirmDialog
          open={verifyDialogOpen}
          onOpenChange={setVerifyDialogOpen}
          title="Verify this payment?"
          description={
            payment ? (
              <p>
                This will poll the MockGateway for the truth and resolve the
                payment to <code>SUCCESS</code> or <code>FAILED</code>.
                <br />
                Payment:{" "}
                <code className="font-mono">{truncateId(payment.id, 8)}</code>
                <br />
                Amount: <strong>{formatMoney(payment.amount)}</strong> · Method:{" "}
                {payment.method}
              </p>
            ) : null
          }
          actionLabel="Verify payment"
          actionVariant="outline"
          loading={verifyLoading}
          onConfirm={doVerify}
        />

        {/* Reversal-request confirmation */}
        <ConfirmDialog
          open={confirmRevOpen}
          onOpenChange={(o) => {
            setConfirmRevOpen(o);
            if (!o) setRevDialogOpen(false);
          }}
          title="Confirm reversal request"
          description={
            payment ? (
              <div>
                <p>
                  This will request a reversal for{" "}
                  <strong>{formatMoney(revAmount)}</strong> on payment{" "}
                  <code className="font-mono">{truncateId(payment.id, 8)}</code>.
                </p>
                <p className="mt-1">
                  The reversal will be in <code>REQUESTED</code> state — a finance
                  manager must approve it before the original payment is reversed
                  and outstanding restored.
                </p>
                <p className="mt-1 text-[11px] text-slate-600">
                  Reason: {revReason.trim() || "—"}
                </p>
              </div>
            ) : null
          }
          actionLabel="Submit reversal request"
          actionVariant="destructive"
          loading={revReqLoading}
          onConfirm={doRequestReversal}
        />

        {/* Approve reversal confirmation */}
        <ConfirmDialog
          open={approveDialogOpen}
          onOpenChange={setApproveDialogOpen}
          title="Approve this reversal?"
          description={
            payment && pendingReversal ? (
              <div>
                <p>
                  Approving will set the reversal to <code>COMPLETED</code>,
                  mark the original payment as <code>REVERSED</code>{" "}
                  (struck-through), void its allocations, and restore the
                  outstanding to the affected installments.
                </p>
                <p className="mt-1">
                  Original amount: <strong>{formatMoney(payment.amount)}</strong>
                  <br />
                  Reversal amount:{" "}
                  <strong>{formatMoney(pendingReversal.amount)}</strong>
                </p>
              </div>
            ) : null
          }
          actionLabel="Approve reversal"
          actionVariant="destructive"
          loading={approveLoading}
          onConfirm={doApproveReversal}
        />
      </DialogContent>
    </Dialog>
  );
}

function Detail({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className="text-xs mt-0.5">{value}</div>
    </div>
  );
}
