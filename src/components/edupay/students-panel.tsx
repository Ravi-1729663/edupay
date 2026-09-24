"use client";

import * as React from "react";
import {
  AlertTriangle,
  ChevronRight,
  Search,
  Users as UsersIcon,
} from "lucide-react";
import { toast } from "sonner";

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
import { StatusBadge } from "@/components/edupay/status-badge";
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
  type Student,
  type StudentOutstanding,
} from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/money";

const PAGE_SIZE = 20;

const STATUS_FILTERS = [
  "ALL",
  "ACTIVE",
  "INACTIVE",
  "GRADUATED",
  "SUSPENDED",
] as const;

interface StudentsPanelProps {
  title?: string;
  /** When provided, clicking a row opens this callback instead of the
   * inline expand (the dashboard wires this to open the StudentFeeAccount
   * modal). When omitted, the inline expand is used. */
  onOpenStudent?: (studentId: string) => void;
}

export function StudentsPanel({
  title = "Students",
  onOpenStudent,
}: StudentsPanelProps) {
  const [q, setQ] = React.useState("");
  const debouncedQ = useDebounced(q.trim(), 350);
  const [status, setStatus] = React.useState<string>("ALL");
  const [offset, setOffset] = React.useState(0);
  const [data, setData] = React.useState<Page<Student> | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<ApiError | null>(null);

  // Inline expand (used when no onOpenStudent is wired up).
  const [expandedId, setExpandedId] = React.useState<string | null>(null);

  React.useEffect(() => setOffset(0), [debouncedQ, status]);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    if (debouncedQ) params.set("q", debouncedQ);
    if (status !== "ALL") params.set("status", status);
    apiFetch<Page<Student>>(`/students?${params.toString()}`)
      .then((p) => {
        if (!cancelled) setData(p);
      })
      .catch((e) => {
        if (cancelled) return;
        const ae =
          e instanceof ApiError ? e : new ApiError(0, "error", "request failed");
        setError(ae);
        toast.error("Failed to load students", { description: ae.message });
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [debouncedQ, status, offset]);

  return (
    <Card className="border-slate-200">
      <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <CardTitle className="flex items-center gap-2 text-lg">
            <UsersIcon className="size-5 text-emerald-700" />
            {title}
          </CardTitle>
          <CardDescription>
            {onOpenStudent
              ? "Click a row to open the student fee account (derived outstanding + drift)."
              : "Click a row to expand the derived outstanding breakdown."}
          </CardDescription>
        </div>
        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
            <Input
              placeholder="Search roll, name, email…"
              className="pl-8"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-full sm:w-40" size="sm">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              {STATUS_FILTERS.map((s) => (
                <SelectItem key={s} value={s}>
                  {s === "ALL" ? "All statuses" : s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? <ErrorState error={error} /> : null}

        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <Table>
            <TableHeader>
              <TableRow>
                {!onOpenStudent ? <TableHead className="w-6" /> : null}
                <TableHead>Roll</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Batch</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableSkeleton rows={6} cols={onOpenStudent ? 6 : 7} />
              ) : data && data.items.length > 0 ? (
                data.items.map((s) => (
                  <StudentRow
                    key={s.id}
                    student={s}
                    expanded={expandedId === s.id}
                    onToggle={() =>
                      onOpenStudent
                        ? onOpenStudent(s.id)
                        : setExpandedId((prev) => (prev === s.id ? null : s.id))
                    }
                    showChevron={!onOpenStudent}
                  />
                ))
              ) : (
                <TableRow>
                  <TableCell
                    colSpan={onOpenStudent ? 6 : 7}
                    className="py-0 px-0 border-0"
                  >
                    <EmptyState
                      title="No students match this search"
                      message="Try clearing the search box or status filter."
                      icon={<UsersIcon className="size-5" />}
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
      </CardContent>
    </Card>
  );
}

function StudentRow({
  student,
  expanded,
  onToggle,
  showChevron,
}: {
  student: Student;
  expanded: boolean;
  onToggle: () => void;
  showChevron: boolean;
}) {
  return (
    <>
      <TableRow
        onClick={onToggle}
        className="cursor-pointer"
        data-state={expanded ? "selected" : undefined}
      >
        {showChevron ? (
          <TableCell>
            <ChevronRight
              className={
                "size-4 transition-transform " +
                (expanded ? "rotate-90 text-emerald-700" : "text-slate-400")
              }
            />
          </TableCell>
        ) : null}
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
      {expanded && showChevron ? (
        <TableRow className="bg-slate-50/70 hover:bg-slate-50/70">
          <TableCell colSpan={7} className="p-4">
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
        const ae =
          e instanceof ApiError ? e : new ApiError(0, "error", "request failed");
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
