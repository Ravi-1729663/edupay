"use client";

import * as React from "react";
import {
  AlertTriangle,
  ChevronRight,
  Search,
  Users as UsersIcon,
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
import { Input } from "@/components/ui/input";
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
import {
  ApiError,
  apiFetch,
  type Page,
  type Student,
  type StudentOutstanding,
} from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/money";

const PAGE_SIZE = 20;

export function StudentsPanel({ title = "Students" }: { title?: string }) {
  const [q, setQ] = React.useState("");
  const [debouncedQ, setDebouncedQ] = React.useState("");
  const [offset, setOffset] = React.useState(0);
  const [data, setData] = React.useState<Page<Student> | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<ApiError | null>(null);

  const [expandedId, setExpandedId] = React.useState<string | null>(null);

  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim()), 350);
    return () => clearTimeout(t);
  }, [q]);

  React.useEffect(() => setOffset(0), [debouncedQ]);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    if (debouncedQ) params.set("q", debouncedQ);
    apiFetch<Page<Student>>(`/students?${params.toString()}`)
      .then((p) => {
        if (!cancelled) setData(p);
      })
      .catch((e) => {
        if (cancelled) return;
        const ae = e instanceof ApiError ? e : new ApiError(0, "error", "request failed");
        setError(ae);
        toast.error("Failed to load students", { description: ae.message });
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [debouncedQ, offset]);

  const total = data?.total ?? 0;
  const from = Math.min(total, offset + 1);
  const to = Math.min(total, offset + (data?.items.length ?? 0));
  const canPrev = offset > 0;
  const canNext = to < total;

  return (
    <Card className="border-slate-200">
      <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg">
            <UsersIcon className="size-5 text-emerald-700" />
            {title}
          </CardTitle>
          <CardDescription>
            Click a row to expand the derived outstanding breakdown.
          </CardDescription>
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
          <Input
            placeholder="Search roll, name, email…"
            className="pl-8"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? (
          <Alert variant="destructive">
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

        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-6" />
                <TableHead>Roll</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Batch</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={6}>
                      <Skeleton className="h-6 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              ) : data && data.items.length > 0 ? (
                data.items.map((s) => (
                  <StudentRow
                    key={s.id}
                    student={s}
                    expanded={expandedId === s.id}
                    onToggle={() =>
                      setExpandedId((prev) => (prev === s.id ? null : s.id))
                    }
                  />
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-slate-500 text-sm py-6">
                    No students found.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>

        <div className="flex items-center justify-between text-xs text-slate-600">
          <span>
            {total === 0
              ? "0 records"
              : `Showing ${from}–${to} of ${total}`}
          </span>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={!canPrev || loading}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={!canNext || loading}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function StudentRow({
  student,
  expanded,
  onToggle,
}: {
  student: Student;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <TableRow
        onClick={onToggle}
        className="cursor-pointer"
        data-state={expanded ? "selected" : undefined}
      >
        <TableCell>
          <ChevronRight
            className={
              "size-4 transition-transform " +
              (expanded ? "rotate-90 text-emerald-700" : "text-slate-400")
            }
          />
        </TableCell>
        <TableCell className="font-mono text-xs">{student.roll_number}</TableCell>
        <TableCell className="font-medium">{student.full_name}</TableCell>
        <TableCell className="font-mono text-xs text-slate-600">
          {student.email}
        </TableCell>
        <TableCell>{student.batch_year}</TableCell>
        <TableCell>
          <StatusBadge status={student.status} />
        </TableCell>
      </TableRow>
      {expanded ? (
        <TableRow className="bg-slate-50/70 hover:bg-slate-50/70">
          <TableCell colSpan={6} className="p-4">
            <OutstandingBreakdown studentId={student.id} />
          </TableCell>
        </TableRow>
      ) : null}
    </>
  );
}

function OutstandingBreakdown({ studentId }: { studentId: string }) {
  const [data, setData] = React.useState<StudentOutstanding | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<ApiError | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiFetch<StudentOutstanding>(`/students/${studentId}/outstanding`)
      .then((o) => !cancelled && setData(o))
      .catch((e) => {
        if (cancelled) return;
        const ae = e instanceof ApiError ? e : new ApiError(0, "error", "request failed");
        setError(ae);
        toast.error("Failed to load outstanding", { description: ae.message });
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [studentId]);

  if (loading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-6 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="size-4" />
        <AlertTitle>{error.code}</AlertTitle>
        <AlertDescription>{error.message}</AlertDescription>
      </Alert>
    );
  }
  if (!data) return null;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <MiniStat label="Total invoiced" value={formatMoney(data.total_invoiced)} />
        <MiniStat label="Concessions" value={formatMoney(data.total_concessions)} />
        <MiniStat label="Allocated" value={formatMoney(data.total_allocated)} />
        <MiniStat
          label="Outstanding"
          value={formatMoney(data.total_outstanding)}
          tone="emerald"
        />
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>#</TableHead>
              <TableHead>Due</TableHead>
              <TableHead className="text-right">Amount</TableHead>
              <TableHead className="text-right">Outstanding</TableHead>
              <TableHead>Cached</TableHead>
              <TableHead>Derived</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.by_installment.map((i) => (
              <TableRow key={i.installment_id} className={i.drift ? "bg-amber-50" : ""}>
                <TableCell>#{i.installment_number}</TableCell>
                <TableCell className="font-mono text-xs">
                  {formatDate(i.due_date)}
                </TableCell>
                <TableCell className="text-right">{formatMoney(i.amount)}</TableCell>
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
            ))}
            {data.by_installment.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-slate-500 text-sm py-4">
                  No installments assigned.
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>
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
