"use client";

import * as React from "react";
import { HelpCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Role } from "@/lib/api";

/**
 * Installment status colours (per the brief):
 *   PENDING=slate, PARTIALLY_PAID=amber, PAID=emerald, OVERDUE=red.
 * Falls back to a muted badge for unknown statuses.
 */
export function StatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const s = (status ?? "").toUpperCase();
  const map: Record<string, string> = {
    PENDING: "border-slate-400 text-slate-700 bg-slate-50",
    PARTIALLY_PAID: "border-amber-400 text-amber-800 bg-amber-50",
    PAID: "border-emerald-500 text-emerald-800 bg-emerald-50",
    OVERDUE: "border-red-500 text-red-700 bg-red-50",
    ACTIVE: "border-emerald-500 text-emerald-800 bg-emerald-50",
    INACTIVE: "border-slate-400 text-slate-600 bg-slate-50",
    GRADUATED: "border-sky-400 text-sky-700 bg-sky-50",
    SUSPENDED: "border-red-400 text-red-600 bg-red-50",
    PENDING_APPROVAL: "border-amber-400 text-amber-800 bg-amber-50",
    APPROVED: "border-emerald-500 text-emerald-800 bg-emerald-50",
    REJECTED: "border-red-500 text-red-700 bg-red-50",
  };
  return (
    <Badge variant="outline" className={cn(map[s] ?? "", className)}>
      {s}
    </Badge>
  );
}

/**
 * Payment status badges (per brief):
 *   SUCCESS=emerald, FAILED=red, PENDING=amber, UNKNOWN=amber+?,
 *   REVERSAL_REQUESTED=amber, REVERSED=slate (struck-through),
 *   CREATED=slate.
 */
export function PaymentStatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const s = (status ?? "").toUpperCase();
  const map: Record<string, string> = {
    CREATED: "border-slate-300 text-slate-600 bg-slate-50",
    PENDING: "border-amber-400 text-amber-800 bg-amber-50",
    SUCCESS: "border-emerald-500 text-emerald-800 bg-emerald-50",
    FAILED: "border-red-500 text-red-700 bg-red-50",
    UNKNOWN: "border-amber-500 text-amber-900 bg-amber-100",
    REVERSAL_REQUESTED: "border-amber-400 text-amber-800 bg-amber-50",
    REVERSED: "border-slate-400 text-slate-500 bg-slate-50 line-through",
  };
  if (s === "UNKNOWN") {
    return (
      <Badge variant="outline" className={cn(map[s], className, "gap-1")}>
        <HelpCircle className="size-3" />
        {s}
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className={cn(map[s] ?? "", className)}>
      {s}
    </Badge>
  );
}

/**
 * Reconciliation classification badges (per brief):
 *   MATCHED=emerald, AMOUNT_MISMATCH=amber,
 *   MISSING_INTERNAL=red, MISSING_EXTERNAL=red, DUPLICATE=red.
 */
export function ReconClassBadge({
  classification,
  className,
}: {
  classification: string;
  className?: string;
}) {
  const s = (classification ?? "").toUpperCase();
  const map: Record<string, string> = {
    MATCHED: "border-emerald-500 text-emerald-800 bg-emerald-50",
    AMOUNT_MISMATCH: "border-amber-400 text-amber-800 bg-amber-50",
    MISSING_INTERNAL: "border-red-500 text-red-700 bg-red-50",
    MISSING_EXTERNAL: "border-red-500 text-red-700 bg-red-50",
    DUPLICATE: "border-red-500 text-red-700 bg-red-50",
  };
  return (
    <Badge variant="outline" className={cn(map[s] ?? "", className)}>
      {s}
    </Badge>
  );
}

/**
 * Role badge colours (avoiding indigo/blue primary). ADMIN=emerald-600,
 * MANAGER=stone-700, STAFF=slate-600, STUDENT=sky-700.
 */
export function RoleBadge({ role, className }: { role: Role; className?: string }) {
  const map: Record<Role, string> = {
    ADMIN: "border-emerald-600 text-emerald-700 bg-emerald-50",
    FINANCE_MANAGER: "border-stone-500 text-stone-700 bg-stone-100",
    FINANCE_STAFF: "border-slate-500 text-slate-700 bg-slate-50",
    STUDENT: "border-teal-500 text-teal-700 bg-teal-50",
  };
  const label: Record<Role, string> = {
    ADMIN: "Admin",
    FINANCE_MANAGER: "Finance Mgr",
    FINANCE_STAFF: "Finance Staff",
    STUDENT: "Student",
  };
  return (
    <Badge variant="outline" className={cn(map[role], className)}>
      {label[role]}
    </Badge>
  );
}
