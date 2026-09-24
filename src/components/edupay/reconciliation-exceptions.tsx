"use client";

import * as React from "react";
import { ArrowLeft, FileSpreadsheet, ListChecks } from "lucide-react";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ReconClassBadge } from "@/components/edupay/status-badge";
import { ConfirmDialog } from "@/components/edupay/confirm-dialog";
import {
  EmptyState,
  ErrorState,
  PaginationBar,
  TableSkeleton,
} from "@/components/edupay/ui-helpers";
import {
  ApiError,
  apiFetch,
  type ReconBatch,
  type ReconClassification,
  type ReconLine,
  type ReconLinePage,
} from "@/lib/api";
import { formatDateTime, formatMoney, truncateId } from "@/lib/money";

const PAGE_SIZE = 25;
const CLASSIFICATIONS: ReconClassification[] = [
  "MATCHED",
  "AMOUNT_MISMATCH",
  "MISSING_INTERNAL",
  "MISSING_EXTERNAL",
  "DUPLICATE",
];

interface ReconciliationExceptionsProps {
  batchId: string;
  onBack?: () => void;
}

/**
 * Lines of a single batch (/reconciliation/lines?batch_id=).
 * Filter by classification dropdown + resolved toggle. Table:
 * external_reference, external_amount, student_id (truncated),
 * payment_id (truncated), classification badge, suggested_payment_id (if any),
 * resolved status. Resolve button → form + confirmation →
 * POST /reconciliation/lines/{id}/resolve.
 */
export function ReconciliationExceptions({
  batchId,
  onBack,
}: ReconciliationExceptionsProps) {
  const [classification, setClassification] = React.useState<string>("ALL");
  const [resolvedFilter, setResolvedFilter] = React.useState<"ALL" | "UNRESOLVED" | "RESOLVED">("ALL");
  const [offset, setOffset] = React.useState(0);
  const [data, setData] = React.useState<ReconLinePage | null>(null);
  const [batch, setBatch] = React.useState<ReconBatch | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<ApiError | null>(null);
  const [seq, setSeq] = React.useState(0);

  // Resolve dialog state.
  const [resolveLine, setResolveLine] = React.useState<ReconLine | null>(null);
  const [resolveClass, setResolveClass] = React.useState<ReconClassification>("MATCHED");
  const [resolveNotes, setResolveNotes] = React.useState("");
  const [resolveOpen, setResolveOpen] = React.useState(false);
  const [resolveLoading, setResolveLoading] = React.useState(false);

  React.useEffect(() => setOffset(0), [classification, resolvedFilter, batchId]);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    params.set("batch_id", batchId);
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    if (classification !== "ALL") params.set("classification", classification);
    if (resolvedFilter === "UNRESOLVED") params.set("resolved", "false");
    if (resolvedFilter === "RESOLVED") params.set("resolved", "true");
    Promise.all([
      apiFetch<ReconBatch>(`/reconciliation/batches/${batchId}`),
      apiFetch<ReconLinePage>(`/reconciliation/lines?${params.toString()}`),
    ])
      .then(([b, p]) => {
        if (cancelled) return;
        setBatch(b);
        setData(p);
      })
      .catch((e) => {
        if (cancelled) return;
        const ae =
          e instanceof ApiError ? e : new ApiError(0, "error", "request failed");
        setError(ae);
        toast.error("Failed to load reconciliation lines", {
          description: ae.message,
        });
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [batchId, classification, resolvedFilter, offset, seq]);

  function openResolve(line: ReconLine) {
    setResolveLine(line);
    setResolveClass(line.classification);
    setResolveNotes(line.notes ?? "");
    setResolveOpen(true);
  }

  async function doResolve() {
    if (!resolveLine) return;
    setResolveLoading(true);
    try {
      await apiFetch(`/reconciliation/lines/${resolveLine.id}/resolve`, {
        method: "POST",
        body: JSON.stringify({
          resolved_classification: resolveClass,
          notes: resolveNotes.trim(),
        }),
      });
      toast.success("Reconciliation line resolved", {
        description: `Pinned as ${resolveClass}`,
      });
      setResolveOpen(false);
      setResolveLine(null);
      setSeq((n) => n + 1);
    } catch (e) {
      const ae =
        e instanceof ApiError ? e : new ApiError(0, "error", String(e));
      toast.error("Resolve failed", { description: ae.message });
      throw e;
    } finally {
      setResolveLoading(false);
    }
  }

  return (
    <Card className="border-slate-200">
      <CardHeader className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          {onBack ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onBack}
              className="text-slate-600"
            >
              <ArrowLeft className="size-4" />
              Batches
            </Button>
          ) : null}
          <ListChecks className="size-5 text-emerald-700" />
          <CardTitle className="text-lg">
            Exception lines —{" "}
            <span className="font-mono text-xs text-slate-500">
              {batch ? batch.source_file_name : truncateId(batchId, 8)}
            </span>
          </CardTitle>
        </div>
        <CardDescription>
          Manually pin unresolved lines to a payment/student. Resolution is
          immutable and never mutates financial truth — it&apos;s a label, not a
          ledger entry.
        </CardDescription>
        <div className="flex flex-col sm:flex-row sm:items-end gap-3">
          <div className="space-y-1">
            <Label className="text-xs">Classification</Label>
            <Select
              value={classification}
              onValueChange={(v) => setClassification(v)}
            >
              <SelectTrigger className="w-full sm:w-44" size="sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All classifications</SelectItem>
                {CLASSIFICATIONS.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Resolved</Label>
            <Select
              value={resolvedFilter}
              onValueChange={(v) => setResolvedFilter(v as typeof resolvedFilter)}
            >
              <SelectTrigger className="w-full sm:w-40" size="sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All</SelectItem>
                <SelectItem value="UNRESOLVED">Unresolved only</SelectItem>
                <SelectItem value="RESOLVED">Resolved only</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <button
            type="button"
            onClick={() => setSeq((n) => n + 1)}
            className="text-xs text-emerald-700 hover:underline sm:ml-auto self-center"
          >
            ↻ Refresh
          </button>
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
                    <TableHead>External ref</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead>Student</TableHead>
                    <TableHead>Payment</TableHead>
                    <TableHead>Classification</TableHead>
                    <TableHead>Suggested</TableHead>
                    <TableHead>Resolved</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableSkeleton rows={6} cols={8} />
                  ) : data && data.items.length > 0 ? (
                    data.items.map((l) => {
                      const isResolved = !!l.resolved_classification;
                      return (
                        <TableRow key={l.id}>
                          <TableCell className="font-mono text-[11px] text-slate-700">
                            {l.external_reference}
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            {formatMoney(l.external_amount)}
                          </TableCell>
                          <TableCell className="font-mono text-[11px] text-slate-500">
                            {l.student_id ? truncateId(l.student_id, 8) : "—"}
                          </TableCell>
                          <TableCell className="font-mono text-[11px] text-slate-500">
                            {l.payment_id ? truncateId(l.payment_id, 8) : "—"}
                          </TableCell>
                          <TableCell>
                            <ReconClassBadge classification={l.classification} />
                          </TableCell>
                          <TableCell className="font-mono text-[11px] text-slate-500">
                            {l.suggested_payment_id
                              ? truncateId(l.suggested_payment_id, 8)
                              : "—"}
                          </TableCell>
                          <TableCell>
                            {isResolved ? (
                              <div className="text-[11px] space-y-0.5">
                                <div className="flex items-center gap-1">
                                  <ReconClassBadge
                                    classification={l.resolved_classification!}
                                  />
                                </div>
                                <div className="text-slate-500">
                                  by{" "}
                                  {l.resolved_by
                                    ? truncateId(l.resolved_by, 8)
                                    : "—"}
                                  {l.resolved_at
                                    ? " · " + formatDateTime(l.resolved_at)
                                    : ""}
                                </div>
                                {l.resolution_notes ? (
                                  <div className="text-slate-700 mt-0.5">
                                    “{l.resolution_notes}”
                                  </div>
                                ) : null}
                              </div>
                            ) : (
                              <span className="text-[11px] text-slate-400">
                                unresolved
                              </span>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            {!isResolved ? (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => openResolve(l)}
                                className="border-emerald-400 text-emerald-700 hover:bg-emerald-50"
                              >
                                Resolve
                              </Button>
                            ) : (
                              <span className="text-[11px] text-slate-400">
                                —
                              </span>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })
                  ) : (
                    <TableRow>
                      <TableCell colSpan={8} className="py-0 px-0 border-0">
                        <EmptyState
                          title="No lines match these filters"
                          message="Try switching the classification or resolved filter, or upload a new batch."
                          icon={<FileSpreadsheet className="size-5" />}
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
          </>
        )}
      </CardContent>

      {/* Resolve confirmation */}
      <ConfirmDialog
        open={resolveOpen}
        onOpenChange={(o) => {
          setResolveOpen(o);
          if (!o) setResolveLine(null);
        }}
        title="Resolve this reconciliation line?"
        description={
          resolveLine ? (
            <div>
              <p>
                External ref:{" "}
                <code className="font-mono">
                  {resolveLine.external_reference}
                </code>
                <br />
                External amount:{" "}
                <strong>{formatMoney(resolveLine.external_amount)}</strong>
              </p>
              <p className="mt-1">
                Pinning classification to{" "}
                <strong>{resolveClass}</strong>. This is immutable — once set,
                it cannot be changed.
              </p>
              <div className="mt-2 space-y-2">
                <div className="space-y-1">
                  <Label className="text-xs">Resolved classification</Label>
                  <Select
                    value={resolveClass}
                    onValueChange={(v) =>
                      setResolveClass(v as ReconClassification)
                    }
                  >
                    <SelectTrigger className="w-full" size="sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CLASSIFICATIONS.map((c) => (
                        <SelectItem key={c} value={c}>
                          {c}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Notes (optional)</Label>
                  <Textarea
                    rows={2}
                    value={resolveNotes}
                    onChange={(e) => setResolveNotes(e.target.value)}
                    placeholder="Why is this line being pinned to this classification?"
                  />
                </div>
              </div>
            </div>
          ) : null
        }
        actionLabel="Confirm resolution"
        actionVariant="destructive"
        loading={resolveLoading}
        onConfirm={doResolve}
      />
    </Card>
  );
}
