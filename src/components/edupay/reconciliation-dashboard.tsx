"use client";

import * as React from "react";
import { FileSpreadsheet, Layers } from "lucide-react";
import { toast } from "sonner";

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
  type ReconBatchPage,
} from "@/lib/api";
import { formatDateTime } from "@/lib/money";

const PAGE_SIZE = 20;

interface ReconciliationDashboardProps {
  onOpenBatch?: (batchId: string) => void;
}

/**
 * List of reconciliation batches (POST /reconciliation/upload creates one).
 * Each row: source_file_name, created_at, counts (matched/mismatch/
 * missing_internal/missing_external/duplicate). Click → Reconciliation
 * Exceptions for that batch.
 */
export function ReconciliationDashboard({ onOpenBatch }: ReconciliationDashboardProps) {
  const [offset, setOffset] = React.useState(0);
  const [data, setData] = React.useState<ReconBatchPage | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<ApiError | null>(null);
  const [seq, setSeq] = React.useState(0);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    apiFetch<ReconBatchPage>(`/reconciliation/batches?${params.toString()}`)
      .then((p) => !cancelled && setData(p))
      .catch((e) => {
        if (cancelled) return;
        const ae =
          e instanceof ApiError ? e : new ApiError(0, "error", "request failed");
        setError(ae);
        toast.error("Failed to load reconciliation batches", {
          description: ae.message,
        });
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [offset, seq]);

  return (
    <Card className="border-slate-200">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Layers className="size-5 text-emerald-700" />
            Reconciliation
          </CardTitle>
          <CardDescription>
            Bank statement batches — each line is auto-classified against the
            internal ledger. Click a batch to drill into the exception lines.
          </CardDescription>
        </div>
        <button
          type="button"
          onClick={() => setSeq((n) => n + 1)}
          className="text-xs text-emerald-700 hover:underline"
        >
          ↻ Refresh
        </button>
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
                    <TableHead>Source file</TableHead>
                    <TableHead>Uploaded</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead className="text-right">Matched</TableHead>
                    <TableHead className="text-right">Mismatch</TableHead>
                    <TableHead className="text-right">Missing int.</TableHead>
                    <TableHead className="text-right">Missing ext.</TableHead>
                    <TableHead className="text-right">Duplicate</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableSkeleton rows={6} cols={8} />
                  ) : data && data.items.length > 0 ? (
                    data.items.map((b: ReconBatch) => (
                      <TableRow
                        key={b.id}
                        className={
                          onOpenBatch
                            ? "cursor-pointer hover:bg-slate-50"
                            : ""
                        }
                        onClick={() => onOpenBatch?.(b.id)}
                      >
                        <TableCell className="font-mono text-xs text-slate-700">
                          <span className="inline-flex items-center gap-1.5">
                            <FileSpreadsheet className="size-3.5 text-slate-500" />
                            {b.source_file_name}
                          </span>
                        </TableCell>
                        <TableCell className="font-mono text-[11px] text-slate-500">
                          {formatDateTime(b.created_at)}
                        </TableCell>
                        <TableCell className="text-right font-semibold">
                          {b.total_lines}
                        </TableCell>
                        <TableCell className="text-right text-emerald-700">
                          {b.matched_count}
                        </TableCell>
                        <TableCell className="text-right text-amber-700">
                          {b.amount_mismatch_count}
                        </TableCell>
                        <TableCell className="text-right text-rose-700">
                          {b.missing_internal_count}
                        </TableCell>
                        <TableCell className="text-right text-rose-700">
                          {b.missing_external_count}
                        </TableCell>
                        <TableCell className="text-right text-rose-700">
                          {b.duplicate_count}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={8} className="py-0 px-0 border-0">
                        <EmptyState
                          title="No reconciliation batches uploaded yet"
                          message="Upload a CSV via POST /reconciliation/upload to start matching bank statements against the ledger."
                          icon={<Layers className="size-5" />}
                        />
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
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
    </Card>
  );
}
