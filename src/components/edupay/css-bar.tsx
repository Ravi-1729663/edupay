"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Pure-CSS horizontal bar chart. NO charting library — just a div whose
 * width is set inline as a percentage. Spec says recharts is installed but
 * should not be used for these dashboards.
 */
export interface CssBarDatum {
  label: string;
  value: number;
  /** Optional display string (defaults to value). */
  display?: string;
  /** Tailwind colour classes for the bar fill + the row chip. */
  colorClass?: string;
}

interface CssBarChartProps {
  data: CssBarDatum[];
  /** Total used to compute widths. If omitted, max value is used. */
  total?: number;
  className?: string;
  /** Empty-state message when data is empty or all-zero. */
  emptyLabel?: string;
}

const DEFAULT_COLORS = [
  "bg-emerald-500",
  "bg-amber-500",
  "bg-rose-500",
  "bg-slate-500",
  "bg-teal-500",
  "bg-stone-500",
];

export function CssBarChart({
  data,
  total,
  className,
  emptyLabel = "No data yet.",
}: CssBarChartProps) {
  const max = total ?? Math.max(1, ...data.map((d) => d.value));
  const sum = data.reduce((a, d) => a + d.value, 0);
  const allZero = sum === 0 || data.length === 0;

  if (allZero) {
    return (
      <div
        className={cn(
          "rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-6 text-center text-xs text-slate-500",
          className,
        )}
      >
        {emptyLabel}
      </div>
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      {data.map((d, i) => {
        const widthPct = Math.max(0, Math.min(100, (d.value / max) * 100));
        const color = d.colorClass ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length];
        return (
          <div key={d.label} className="space-y-0.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-slate-700">{d.label}</span>
              <span className="font-mono text-slate-600">
                {d.display ?? d.value}
              </span>
            </div>
            <div
              className="h-2.5 w-full rounded-full bg-slate-100 overflow-hidden"
              role="progressbar"
              aria-valuenow={d.value}
              aria-valuemin={0}
              aria-valuemax={max}
            >
              <div
                className={cn("h-full rounded-full transition-all", color)}
                style={{ width: `${widthPct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** A single big KPI card. */
export function KpiCard({
  label,
  value,
  sub,
  tone = "slate",
  icon,
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: "emerald" | "amber" | "rose" | "slate";
  icon?: React.ReactNode;
}) {
  const toneMap: Record<string, string> = {
    emerald:
      "border-emerald-200 bg-emerald-50 text-emerald-800",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    rose: "border-rose-200 bg-rose-50 text-rose-800",
    slate: "border-slate-200 bg-white text-slate-800",
  };
  return (
    <div className={cn("rounded-lg border p-3", toneMap[tone])}>
      <div className="flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-wide opacity-80">
          {label}
        </div>
        {icon ? <div className="opacity-70">{icon}</div> : null}
      </div>
      <div className="mt-1 text-xl font-semibold">{value}</div>
      {sub ? <div className="text-[11px] opacity-70 mt-0.5">{sub}</div> : null}
    </div>
  );
}
