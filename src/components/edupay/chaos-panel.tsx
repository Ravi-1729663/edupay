"use client";

import * as React from "react";
import { Beaker, Info, Loader2 } from "lucide-react";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import {
  ApiError,
  apiFetch,
  type ChaosMode,
  type ChaosSetting,
} from "@/lib/api";

const CHAOS_MODES: {
  mode: ChaosMode;
  description: string;
}[] = [
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
      "MockGateway fires the callback N seconds late. Tests UNKNOWN handling and reconciliation tolerance.",
  },
];

interface ChaosPanelProps {
  /** Compact variant for embedding in the STUDENT view (default = full). */
  variant?: "full" | "compact";
}

/**
 * Dev-only chaos panel — wired for real (Package D).
 *
 * GET /mock-gateway/chaos returns the current setting. Clicking a mode
 * POSTs /mock-gateway/chaos {mode, delay_seconds}. The setting applies to
 * the NEXT payment initiated through the gateway (no effect on past ones).
 */
export function ChaosPanel({ variant = "full" }: ChaosPanelProps) {
  const [setting, setSetting] = React.useState<ChaosSetting | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [posting, setPosting] = React.useState<ChaosMode | null>(null);
  const [error, setError] = React.useState<ApiError | null>(null);
  const [delaySeconds, setDelaySeconds] = React.useState<number>(60);
  const [seq, setSeq] = React.useState(0);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiFetch<ChaosSetting>("/mock-gateway/chaos")
      .then((s) => {
        if (cancelled) return;
        setSetting(s);
        setDelaySeconds(s.delay_seconds ?? 60);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(
          e instanceof ApiError ? e : new ApiError(0, "error", String(e)),
        );
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [seq]);

  async function setMode(mode: ChaosMode) {
    setPosting(mode);
    try {
      const s = await apiFetch<ChaosSetting>("/mock-gateway/chaos", {
        method: "POST",
        body: JSON.stringify({
          mode,
          delay_seconds: mode === "LATE_CALLBACK" ? delaySeconds : 0,
        }),
      });
      setSetting(s);
      toast.success(`Chaos mode set to ${mode}`, {
        description: "Applies to the next payment initiated.",
      });
    } catch (e) {
      const ae =
        e instanceof ApiError ? e : new ApiError(0, "error", String(e));
      toast.error("Failed to set chaos mode", { description: ae.message });
    } finally {
      setPosting(null);
    }
  }

  return (
    <Card
      className={cn(
        "border-dashed border-amber-300 bg-amber-50/40",
        variant === "compact" && "border",
      )}
    >
      <CardHeader className="flex flex-row items-start gap-3 space-y-0">
        <div className="mt-1 size-9 rounded-lg border border-amber-300 bg-amber-100 flex items-center justify-center">
          <Beaker className="size-5 text-amber-700" />
        </div>
        <div className="space-y-1 flex-1">
          <CardTitle className="flex items-center gap-2 text-base">
            Chaos panel
            <Badge
              variant="outline"
              className="border-amber-400 text-amber-800 bg-amber-50"
            >
              dev only · ADMIN
            </Badge>
          </CardTitle>
          <CardDescription>
            Toggle MockGateway outcomes for the next initiated payment. The
            setting applies only to NEW payments.
          </CardDescription>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-[11px] uppercase tracking-wide text-slate-500">
              Current:
            </span>
            {loading ? (
              <Loader2 className="size-4 animate-spin text-amber-700" />
            ) : setting ? (
              <Badge
                variant="outline"
                className="border-amber-500 text-amber-900 bg-amber-100 font-mono"
              >
                {setting.mode}
                {setting.mode === "LATE_CALLBACK" && setting.delay_seconds
                  ? ` · +${setting.delay_seconds}s`
                  : ""}
              </Badge>
            ) : (
              <span className="text-xs text-slate-500">unavailable</span>
            )}
            <button
              type="button"
              onClick={() => setSeq((n) => n + 1)}
              className="text-[11px] text-emerald-700 hover:underline ml-auto"
            >
              ↻ refresh
            </button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {error ? (
          <Alert variant="destructive">
            <AlertTitle>
              {error.code} (HTTP {error.status || "?"})
            </AlertTitle>
            <AlertDescription>
              {error.message}
              {error.requestId ? (
                <p className="font-mono text-[11px] opacity-80 mt-0.5">
                  request_id: {error.requestId}
                </p>
              ) : null}
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {CHAOS_MODES.map((m) => {
            const isCurrent = setting?.mode === m.mode;
            const isPosting = posting === m.mode;
            return (
              <Tooltip key={m.mode}>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    disabled={isPosting}
                    onClick={() => setMode(m.mode)}
                    className={cn(
                      "text-left rounded-md border px-3 py-2 text-xs transition-colors disabled:opacity-60 disabled:cursor-not-allowed",
                      isCurrent
                        ? "border-amber-500 bg-amber-100 text-amber-900"
                        : "border-slate-200 bg-white hover:border-amber-400 hover:bg-amber-50",
                    )}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono font-semibold text-slate-800">
                        {m.mode}
                      </span>
                      {isCurrent ? (
                        <span className="ml-auto text-[10px] text-amber-700 uppercase">
                          active
                        </span>
                      ) : null}
                      {isPosting ? (
                        <Loader2 className="size-3 animate-spin ml-auto" />
                      ) : null}
                    </div>
                    <div className="text-slate-500 line-clamp-2 mt-1">
                      {m.description}
                    </div>
                  </button>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">
                  <div className="space-y-1">
                    <div className="font-mono font-semibold">{m.mode}</div>
                    <div className="text-[11px] leading-snug">
                      {m.description}
                    </div>
                  </div>
                </TooltipContent>
              </Tooltip>
            );
          })}
        </div>

        <div className="rounded-md border border-amber-200 bg-amber-50/50 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <Label htmlFor="delay" className="text-xs text-amber-900">
              LATE_CALLBACK delay (seconds)
            </Label>
          </div>
          <div className="flex items-center gap-2">
            <Input
              id="delay"
              type="number"
              min={1}
              max={600}
              value={delaySeconds}
              onChange={(e) =>
                setDelaySeconds(Math.max(1, Number(e.target.value || 0)))
              }
              className="w-24 font-mono"
            />
            <button
              type="button"
              onClick={() => setMode("LATE_CALLBACK")}
              disabled={posting !== null}
              className="text-xs text-amber-800 hover:underline disabled:opacity-50"
            >
              Apply to LATE_CALLBACK
            </button>
          </div>
        </div>

        <p className="text-[11px] text-slate-500 flex items-start gap-1.5">
          <Info className="size-3.5 shrink-0 mt-0.5" />
          Selecting a mode POSTs <code>/mock-gateway/chaos</code>. The setting
          applies only to the next payment — past payments keep their original
          outcome ledger.
        </p>
      </CardContent>
    </Card>
  );
}
