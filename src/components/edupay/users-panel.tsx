"use client";

import * as React from "react";
import { Search, Users } from "lucide-react";
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
import { RoleBadge } from "@/components/edupay/status-badge";
import {
  ApiError,
  apiFetch,
  type Page,
  type User,
} from "@/lib/api";

const PAGE_SIZE = 20;

export function UsersPanel() {
  const [q, setQ] = React.useState("");
  const [debouncedQ, setDebouncedQ] = React.useState("");
  const [offset, setOffset] = React.useState(0);
  const [data, setData] = React.useState<Page<User> | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<ApiError | null>(null);

  // Debounce search input.
  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim()), 350);
    return () => clearTimeout(t);
  }, [q]);

  // Reset offset when query changes.
  React.useEffect(() => setOffset(0), [debouncedQ]);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    if (debouncedQ) params.set("q", debouncedQ);
    apiFetch<Page<User>>(`/users?${params.toString()}`)
      .then((p) => {
        if (!cancelled) setData(p);
      })
      .catch((e) => {
        if (cancelled) return;
        const ae = e instanceof ApiError ? e : new ApiError(0, "error", "request failed");
        setError(ae);
        toast.error("Failed to load users", { description: ae.message });
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
            <Users className="size-5 text-emerald-700" />
            Users
          </CardTitle>
          <CardDescription>Manage staff, managers, and admins.</CardDescription>
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
          <Input
            placeholder="Search email or name…"
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
                <TableHead>Email</TableHead>
                <TableHead>Full name</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={4}>
                      <Skeleton className="h-6 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              ) : data && data.items.length > 0 ? (
                data.items.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell className="font-mono text-xs">{u.email}</TableCell>
                    <TableCell className="font-medium">{u.full_name}</TableCell>
                    <TableCell>
                      <RoleBadge role={u.role} />
                    </TableCell>
                    <TableCell>
                      {u.is_active ? (
                        <span className="text-emerald-700 text-xs">active</span>
                      ) : (
                        <span className="text-red-700 text-xs">inactive</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-slate-500 text-sm py-6">
                    No users found.
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
