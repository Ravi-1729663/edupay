"use client";

import * as React from "react";
import { Beaker, Info } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Badge } from "@/components/ui/badge";

const CHAOS_MODES: { mode: string; description: string }[] = [
  {
    mode: "SUCCESS",
    description:
      "MockGateway returns SUCCESS and immediately fires the webhook. Happy path.",
  },
  {
    mode: "FAILED",
    description:
      "MockGateway returns FAILED and fires a FAILED webhook. No reversal — reversal is a separate manual flow.",
  },
  {
    mode: "TIMEOUT_NO_CALLBACK",
    description:
      "MockGateway never fires a callback. Payment stays PENDING → an operator must call /payments/{id}/verify.",
  },
  {
    mode: "DUPLICATE_CALLBACK",
    description:
      "MockGateway fires the same callback twice. Webhook must be idempotent on gateway_ref.",
  },
  {
    mode: "LATE_CALLBACK",
    description:
      "MockGateway fires the callback 60+ seconds late. Tests UNKNOWN handling and reconciliation tolerance.",
  },
];

/**
 * Dev-only placeholder chaos panel. The brief requires the five chaos
 * modes to be visibly present even though clicking does nothing —
 * wiring lives in Package B (when /mock-gateway/chaos lands).
 */
export function ChaosPanel() {
  return (
    <Card className="border-dashed border-amber-300 bg-amber-50/40">
      <CardHeader className="flex flex-row items-start gap-3 space-y-0">
        <div className="mt-1 size-9 rounded-lg border border-amber-300 bg-amber-100 flex items-center justify-center">
          <Beaker className="size-5 text-amber-700" />
        </div>
        <div className="space-y-1">
          <CardTitle className="flex items-center gap-2 text-base">
            Chaos panel
            <Badge variant="outline" className="border-amber-400 text-amber-800 bg-amber-50">
              dev only · Package B
            </Badge>
          </CardTitle>
          <CardDescription>
            Will toggle MockGateway outcomes for the next initiated payment.
            Disabled in Package A — payment initiation is delivered in
            Package&nbsp;B.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {CHAOS_MODES.map((m) => (
            <Tooltip key={m.mode}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  disabled
                  className="text-left rounded-md border border-slate-200 bg-white px-3 py-2 text-xs disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  <div className="font-mono font-semibold text-slate-800">
                    {m.mode}
                  </div>
                  <div className="text-slate-500 line-clamp-2">
                    {m.description}
                  </div>
                </button>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <div className="space-y-1">
                  <div className="font-mono font-semibold">{m.mode}</div>
                  <div className="text-[11px] leading-snug">{m.description}</div>
                </div>
              </TooltipContent>
            </Tooltip>
          ))}
        </div>
        <p className="mt-3 text-[11px] text-slate-500 flex items-center gap-1.5">
          <Info className="size-3.5" />
          Buttons are intentionally inert — they will be wired in Package B.
        </p>
      </CardContent>
    </Card>
  );
}
