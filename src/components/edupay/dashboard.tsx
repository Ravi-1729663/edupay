"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  GraduationCap,
  LogOut,
  ScrollText,
  ShieldCheck,
  Users as UsersIcon,
  Wallet,
} from "lucide-react";
import Image from "next/image";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
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
import { RoleBadge } from "@/components/edupay/status-badge";
import { IntegrityPanel } from "@/components/edupay/integrity-panel";
import { StudentsPanel } from "@/components/edupay/students-panel";
import { UsersPanel } from "@/components/edupay/users-panel";
import { StudentFees } from "@/components/edupay/student-fees";
import { Footer } from "@/components/edupay/footer";
import {
  ApiError,
  apiFetch,
  clearToken,
  type AuditLog,
  type AuditPage,
  type Role,
  type User,
} from "@/lib/api";
import { formatDateTime } from "@/lib/money";

interface DashboardProps {
  user: User;
  onSignOut: () => void;
}

type TabKey = "users" | "integrity" | "audit" | "students" | "fees";

export function Dashboard({ user, onSignOut }: DashboardProps) {
  const role: Role = user.role;

  // Decide which tabs are visible for this role.
  const tabs: { key: TabKey; label: string; icon: React.ReactNode }[] = [];
  if (role === "ADMIN") {
    tabs.push(
      { key: "users", label: "Users", icon: <UsersIcon className="size-4" /> },
      { key: "integrity", label: "Integrity", icon: <ShieldCheck className="size-4" /> },
      { key: "audit", label: "Audit logs", icon: <ScrollText className="size-4" /> },
      { key: "students", label: "Students", icon: <GraduationCap className="size-4" /> },
    );
  } else if (role === "FINANCE_MANAGER") {
    tabs.push(
      { key: "students", label: "Students", icon: <GraduationCap className="size-4" /> },
      { key: "integrity", label: "Integrity", icon: <ShieldCheck className="size-4" /> },
      { key: "audit", label: "Audit logs", icon: <ScrollText className="size-4" /> },
    );
  } else if (role === "FINANCE_STAFF") {
    tabs.push({ key: "students", label: "Students", icon: <GraduationCap className="size-4" /> });
  } else {
    // STUDENT
    tabs.push({ key: "fees", label: "My fees", icon: <Wallet className="size-4" /> });
  }

  const [activeTab, setActiveTab] = React.useState<TabKey>(tabs[0].key);

  function handleSignOut() {
    clearToken();
    onSignOut();
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <Image
              src="/logo.svg"
              alt="EduPay"
              width={28}
              height={28}
              className="size-7"
              priority
            />
            <span className="font-semibold text-slate-900 tracking-tight">
              EduPay
            </span>
            <Badge
              variant="outline"
              className="border-emerald-300 text-emerald-700 bg-emerald-50"
            >
              Package A
            </Badge>
          </div>

          <div className="flex items-center gap-2.5">
            <div className="hidden sm:flex flex-col items-end leading-tight">
              <span className="text-sm font-medium text-slate-800">
                {user.full_name}
              </span>
              <span className="text-[11px] text-slate-500 font-mono">
                {user.email}
              </span>
            </div>
            <RoleBadge role={role} />
            <Button
              size="sm"
              variant="outline"
              onClick={handleSignOut}
              className="border-slate-300 text-slate-700 hover:bg-slate-100"
            >
              <LogOut className="size-4" />
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1 mx-auto max-w-7xl w-full px-4 sm:px-6 lg:px-8 py-6">
        <Tabs
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as TabKey)}
          className="gap-4"
        >
          <TabsList className="bg-slate-100 border border-slate-200">
            {tabs.map((t) => (
              <TabsTrigger key={t.key} value={t.key} className="gap-1.5">
                {t.icon}
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>

          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15 }}
            >
              {activeTab === "users" && role === "ADMIN" ? <UsersPanel /> : null}
              {activeTab === "integrity" &&
              (role === "ADMIN" || role === "FINANCE_MANAGER") ? (
                <IntegrityPanel />
              ) : null}
              {activeTab === "audit" &&
              (role === "ADMIN" || role === "FINANCE_MANAGER") ? (
                <AuditLogsPanel />
              ) : null}
              {activeTab === "students" &&
              (role === "ADMIN" ||
                role === "FINANCE_MANAGER" ||
                role === "FINANCE_STAFF") ? (
                <StudentsPanel />
              ) : null}
              {activeTab === "fees" && role === "STUDENT" && user.student_id ? (
                <StudentFees studentId={user.student_id} />
              ) : null}
            </motion.div>
          </AnimatePresence>
        </Tabs>
      </main>

      <Footer />
    </div>
  );
}

/**
 * Lightweight audit log panel. Paginated server-side (no UI nav — just the
 * latest 50). ADMIN & FINANCE_MANAGER only.
 */
function AuditLogsPanel() {
  const [data, setData] = React.useState<AuditLog[] | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<ApiError | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiFetch<AuditPage>(`/admin/audit-logs?limit=50`)
      .then((p) => !cancelled && setData(p.items))
      .catch((e) => {
        if (cancelled) return;
        const ae = e instanceof ApiError ? e : new ApiError(0, "error", "request failed");
        setError(ae);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <ScrollText className="size-5 text-emerald-700" />
        <h3 className="font-semibold text-slate-900">Audit logs</h3>
        <span className="text-xs text-slate-500">latest 50</span>
      </div>
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>{error.code}</AlertTitle>
          <AlertDescription>
            {error.message}
            {error.requestId ? ` · ${error.requestId}` : ""}
          </AlertDescription>
        </Alert>
      ) : null}

      {loading ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Entity</TableHead>
                <TableHead>Actor</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data && data.length > 0 ? (
                data.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-mono text-[11px] text-slate-600">
                      {formatDateTime(row.ts)}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{row.action}</TableCell>
                    <TableCell className="text-xs">
                      <span className="font-mono text-slate-700">
                        {row.entity_type}
                      </span>
                      {row.entity_id ? (
                        <span className="text-slate-500">
                          {" "}
                          · {row.entity_id.slice(0, 8)}…
                        </span>
                      ) : null}
                    </TableCell>
                    <TableCell className="font-mono text-[11px] text-slate-500">
                      {row.actor_user_id ? row.actor_user_id.slice(0, 8) + "…" : "—"}
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-slate-500 text-sm py-6">
                    No audit entries.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
