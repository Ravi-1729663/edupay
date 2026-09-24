"use client";

import * as React from "react";
import {
  Banknote,
  Beaker,
  GraduationCap,
  History,
  Layers,
  Menu,
  ScrollText,
  ShieldCheck,
  Users as UsersIcon,
  Wallet,
  X,
} from "lucide-react";
import Image from "next/image";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { RoleBadge } from "@/components/edupay/status-badge";
import type { Role, User } from "@/lib/api";

export type ViewKey =
  | "finance"
  | "students"
  | "payments"
  | "fees"
  | "recon"
  | "recon-exceptions"
  | "audit"
  | "integrity"
  | "users"
  | "chaos";

interface NavItem {
  key: ViewKey;
  label: string;
  icon: React.ReactNode;
}

/** Build the role-aware list of nav items. */
export function navForRole(role: Role): NavItem[] {
  const items: NavItem[] = [];
  if (role === "STUDENT") {
    items.push({ key: "fees", label: "My fees", icon: <Wallet className="size-4" /> });
    items.push({
      key: "payments",
      label: "My payments",
      icon: <History className="size-4" />,
    });
    return items;
  }
  // Staff / manager / admin all see Students + Payments.
  items.push({
    key: "students",
    label: "Students",
    icon: <GraduationCap className="size-4" />,
  });
  items.push({
    key: "payments",
    label: "Payments",
    icon: <History className="size-4" />,
  });
  if (role === "FINANCE_MANAGER" || role === "ADMIN") {
    items.push({
      key: "finance",
      label: "Finance",
      icon: <Banknote className="size-4" />,
    });
    items.push({
      key: "recon",
      label: "Reconciliation",
      icon: <Layers className="size-4" />,
    });
    items.push({
      key: "audit",
      label: "Audit",
      icon: <ScrollText className="size-4" />,
    });
    items.push({
      key: "integrity",
      label: "Integrity",
      icon: <ShieldCheck className="size-4" />,
    });
  }
  if (role === "ADMIN") {
    items.push({
      key: "users",
      label: "Users",
      icon: <UsersIcon className="size-4" />,
    });
    items.push({
      key: "chaos",
      label: "Chaos",
      icon: <Beaker className="size-4" />,
    });
  }
  return items;
}

interface NavProps {
  user: User;
  activeView: ViewKey;
  onChange: (v: ViewKey) => void;
  onSignOut: () => void;
  /** When true, the nav item's children render in the main panel
   * instead of switching tabs. Used for the "Reconciliation → Exceptions"
   * sub-view (which carries a batchId). */
  rightSlot?: React.ReactNode;
}

/**
 * Sticky top bar with EduPay logo + role-aware nav. On mobile the nav
 * collapses into a dropdown hamburger.
 */
export function Nav({ user, activeView, onChange, onSignOut, rightSlot }: NavProps) {
  const items = navForRole(user.role);
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80 print:hidden">
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
          <span className="font-semibold text-slate-900 tracking-tight hidden sm:inline">
            EduPay
          </span>
          <Badge
            variant="outline"
            className="border-emerald-300 text-emerald-700 bg-emerald-50 hidden md:inline-flex"
          >
            Package D
          </Badge>
        </div>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-1">
          {items.map((it) => {
            const active = activeView === it.key;
            return (
              <button
                key={it.key}
                type="button"
                onClick={() => onChange(it.key)}
                className={
                  "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors " +
                  (active
                    ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                    : "text-slate-600 hover:bg-slate-100 border border-transparent")
                }
                aria-current={active ? "page" : undefined}
              >
                {it.icon}
                {it.label}
              </button>
            );
          })}
        </nav>

        <div className="flex items-center gap-2.5">
          {rightSlot}
          <div className="hidden sm:flex flex-col items-end leading-tight">
            <span className="text-sm font-medium text-slate-800 max-w-[14rem] truncate">
              {user.full_name}
            </span>
            <span className="text-[11px] text-slate-500 font-mono max-w-[14rem] truncate">
              {user.email}
            </span>
          </div>
          <RoleBadge role={user.role} />
          <Button
            size="sm"
            variant="outline"
            onClick={onSignOut}
            className="border-slate-300 text-slate-700 hover:bg-slate-100 hidden sm:inline-flex"
          >
            Sign out
          </Button>

          {/* Mobile menu */}
          <div className="md:hidden">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm" variant="outline" className="px-2">
                  <Menu className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="font-normal">
                  <div className="flex flex-col gap-0.5">
                    <span className="text-sm">{user.full_name}</span>
                    <span className="font-mono text-[11px] text-slate-500">
                      {user.email}
                    </span>
                    <div className="mt-1">
                      <RoleBadge role={user.role} />
                    </div>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                {items.map((it) => (
                  <DropdownMenuItem
                    key={it.key}
                    onClick={() => onChange(it.key)}
                    className={
                      activeView === it.key
                        ? "bg-emerald-50 text-emerald-800"
                        : ""
                    }
                  >
                    <span className="inline-flex items-center gap-2">
                      {it.icon}
                      {it.label}
                    </span>
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={onSignOut}
                  className="text-rose-700 focus:bg-rose-50"
                >
                  <X className="size-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>
    </header>
  );
}
