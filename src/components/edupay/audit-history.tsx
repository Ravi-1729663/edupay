"use client";

import * as React from "react";
import { ChevronDown, ChevronRight, ScrollText } from "lucide-react";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
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
  type AuditLog,
  type AuditPage,
} from "@/lib/api";
import { formatDateTime, truncateId } from "@/lib/money";

const PAGE_SIZE = 50;

/**
 * Full audit history: GET /admin/audit-logs with filters
 * (entity_type, entity_id, actor_user_id) + pagination. Table:
 * ts, actor_user_id (truncated), action, entity_type, entity_id
 * (truncated), metadata (expandable JSON).
 */
export function AuditHistory() {
  const [entityType, setEntityType] = React.useState("");
  const [entityId, setEntityId] = React.useState("");
  const [actorId, setActorId] = React.useState("");
  const debouncedEntityType = useDebounced(entityType.trim(), 300);
  const debouncedEntityId = useDebounced(entityId.trim(), 300);
  const debouncedActorId = useDebounced(actorId.trim(), 300);

  const [offset, setOffset] = React.useState(0);
  const [data, setData] = React.useState<AuditPage | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<ApiError | null>(null);
  const [seq, setSeq] = React.useState(0);

  React.useEffect(
    () => setOffset(0),
    [debouncedEntityType, debouncedEntityId, debouncedActorId],
  );

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    if (debouncedEntityType) params.set("entity_type", debouncedEntityType);
    if (debouncedEntityId) params.set("entity_id", debouncedEntityId);
    if (debouncedActorId) params.set("actor_user_id", debouncedActorId);
    apiFetch<AuditPage>(`/admin/audit-logs?${params.toString()}`)
      .then((p) => !cancelled && setData(p))
      .catch((e) => {
        if (cancelled) return;
        const ae =
          e instanceof ApiError ? e : new ApiError(0, "error", "request failed");
        setError(ae);
        toast.error("Failed to load audit logs", { description: ae.message });
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [debouncedEntityType, debouncedEntityId, debouncedActorId, offset, seq]);

  return (
    <Card className="border-slate-200">
      <CardHeader className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <ScrollText className="size-5 text-emerald-700" />
              Audit history
            </CardTitle>
            <CardDescription>
              Every state transition is logged here. Filter by entity, actor,
              or both.
            </CardDescription>
          </div>
          <button
            type="button"
            onClick={() => setSeq((n) => n + 1)}
            className="text-xs text-emerald-700 hover:underline"
          >
            ↻ Refresh
          </button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <div className="space-y-1">
            <Label htmlFor="aud-et" className="text-xs">
              Entity type
            </Label>
            <Input
              id="aud-et"
              placeholder="payment / installment / …"
              value={entityType}
              onChange={(e) => setEntityType(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="aud-ei" className="text-xs">
              Entity id
            </Label>
            <Input
              id="aud-ei"
              placeholder="full or partial UUID"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              className="font-mono"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="aud-ai" className="text-xs">
              Actor user id
            </Label>
            <Input
              id="aud-ai"
              placeholder="full or partial UUID"
              value={actorId}
              onChange={(e) => setActorId(e.target.value)}
              className="font-mono"
            />
          </div>
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
                    <TableHead>When</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Entity</TableHead>
                    <TableHead>Metadata</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableSkeleton rows={8} cols={5} />
                  ) : data && data.items.length > 0 ? (
                    data.items.map((row: AuditLog) => (
                      <AuditRow key={row.id} row={row} />
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={5} className="py-0 px-0 border-0">
                        <EmptyState
                          title="No audit entries match these filters"
                          message="Try clearing the filters or widening the search."
                          icon={<ScrollText className="size-5" />}
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
              pageItems={data?.items.length ?? 0}
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

function AuditRow({ row }: { row: AuditLog }) {
  const [open, setOpen] = React.useState(false);
  const hasMeta = !!row.metadata && Object.keys(row.metadata).length > 0;
  return (
    <Collapsible open={open} onOpenChange={setOpen} asChild>
      <>
        <TableRow>
          <TableCell className="font-mono text-[11px] text-slate-600">
            {row.ts ? formatDateTime(row.ts) : "—"}
          </TableCell>
          <TableCell className="font-mono text-[11px] text-slate-500">
            {row.actor_user_id ? truncateId(row.actor_user_id, 8) : "—"}
          </TableCell>
          <TableCell>
            <Badge
              variant="outline"
              className="border-slate-300 text-slate-700 bg-slate-50 font-mono text-[11px]"
            >
              {row.action}
            </Badge>
          </TableCell>
          <TableCell className="text-xs">
            <span className="font-mono text-slate-700">{row.entity_type}</span>
            {row.entity_id ? (
              <span className="text-slate-500"> · {truncateId(row.entity_id, 8)}</span>
            ) : null}
          </TableCell>
          <TableCell>
            {hasMeta ? (
              <CollapsibleTrigger asChild>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 text-[11px] text-emerald-700 hover:underline"
                >
                  {open ? (
                    <ChevronDown className="size-3" />
                  ) : (
                    <ChevronRight className="size-3" />
                  )}
                  {Object.keys(row.metadata!).length} field
                  {Object.keys(row.metadata!).length === 1 ? "" : "s"}
                </button>
              </CollapsibleTrigger>
            ) : (
              <span className="text-[11px] text-slate-400">—</span>
            )}
          </TableCell>
        </TableRow>
        {hasMeta ? (
          <TableRow className="bg-slate-50/70 hover:bg-slate-50/70">
            <TableCell colSpan={5} className="p-2">
              <CollapsibleContent>
                <pre className="text-[11px] font-mono text-slate-700 bg-white border border-slate-200 rounded-md p-2 overflow-x-auto">
                  {JSON.stringify(row.metadata, null, 2)}
                </pre>
              </CollapsibleContent>
            </TableCell>
          </TableRow>
        ) : null}
      </>
    </Collapsible>
  );
}
