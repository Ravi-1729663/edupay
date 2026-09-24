"use client";

import * as React from "react";
import { toast } from "sonner";
import { GraduationCap, Loader2, LogIn } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, apiFetch, setToken, type TokenResponse, type User } from "@/lib/api";

const DEMO_LOGINS: { role: string; email: string; password: string }[] = [
  { role: "Admin", email: "admin@edupay.college", password: "Password123!" },
  { role: "Finance Mgr", email: "manager@edupay.college", password: "Password123!" },
  { role: "Finance Staff", email: "staff@edupay.college", password: "Password123!" },
  { role: "Student", email: "student@edupay.college", password: "Password123!" },
];

/** Pings /health on the backend via the proxy; shows green/red dot. */
function BackendStatus() {
  const [state, setState] = React.useState<
    "checking" | "ok" | "down"
  >("checking");
  const [msg, setMsg] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setState("checking");
    setMsg(null);
    fetch("/api/edupay/health", { cache: "no-store" })
      .then(async (r) => {
        if (cancelled) return;
        if (r.ok) {
          // Validate the body shape — backend should say {"status":"ok"}.
          try {
            const body = await r.json();
            if (body?.status === "ok") {
              setState("ok");
            } else {
              setState("down");
              setMsg("unexpected body");
            }
          } catch {
            // Empty body but 2xx — assume ok.
            setState("ok");
          }
        } else {
          setState("down");
          setMsg(
            r.status >= 500
              ? "backend not running on :8000"
              : `HTTP ${r.status}`,
          );
        }
      })
      .catch((e) => {
        if (cancelled) return;
        setState("down");
        setMsg(e instanceof Error ? e.message : "network error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
      <span
        className={
          "size-2 rounded-full inline-block " +
          (state === "checking"
            ? "bg-slate-300 animate-pulse"
            : state === "ok"
              ? "bg-emerald-500"
              : "bg-rose-500")
        }
        aria-label={`backend ${state}`}
      />
      <span className="font-mono">
        backend{" "}
        {state === "checking"
          ? "checking…"
          : state === "ok"
            ? "online"
            : "offline"}
      </span>
      {msg ? <span className="text-rose-600"> · {msg}</span> : null}
    </div>
  );
}

export function LoginCard({ onSignedIn }: { onSignedIn: (u: User) => void }) {
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  async function submit(e?: React.FormEvent) {
    e?.preventDefault();
    if (loading) return;
    setLoading(true);
    try {
      const tok = await apiFetch<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setToken(tok.access_token);
      onSignedIn(tok.user);
      toast.success(`Welcome, ${tok.user.full_name}`);
    } catch (err) {
      const ae = err instanceof ApiError ? err : undefined;
      toast.error(ae?.message ?? "Login failed", {
        description: ae ? `${ae.code} · ${ae.requestId ?? ""}` : undefined,
      });
    } finally {
      setLoading(false);
    }
  }

  function fillAndFocus(d: (typeof DEMO_LOGINS)[number]) {
    setEmail(d.email);
    setPassword(d.password);
  }

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-gradient-to-b from-slate-50 to-stone-100 px-4 py-10">
      <Card className="w-full max-w-md shadow-lg border-slate-200">
        <CardHeader className="items-center text-center gap-3">
          <div className="mx-auto size-12 rounded-xl bg-emerald-600/10 border border-emerald-200 flex items-center justify-center">
            <GraduationCap className="size-6 text-emerald-700" />
          </div>
          <CardTitle className="text-2xl">EduPay</CardTitle>
          <CardDescription>
            College fee collection system. Sign in to continue.
          </CardDescription>
          <BackendStatus />
        </CardHeader>
        <form onSubmit={submit}>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@edupay.college"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-3">
            <Button
              type="submit"
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
              disabled={loading}
            >
              {loading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <LogIn className="size-4" />
              )}
              Sign in
            </Button>
          </CardFooter>
        </form>
        <div className="px-6 pb-6">
          <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-3">
            <p className="text-xs font-medium text-slate-700 mb-2">
              Demo logins (password <code className="font-mono">Password123!</code>)
            </p>
            <div className="grid grid-cols-2 gap-2">
              {DEMO_LOGINS.map((d) => (
                <button
                  key={d.email}
                  type="button"
                  onClick={() => fillAndFocus(d)}
                  className="text-left text-xs rounded-md border border-slate-200 bg-white px-2.5 py-1.5 hover:border-emerald-400 hover:bg-emerald-50 transition-colors"
                >
                  <div className="font-medium text-slate-800">{d.role}</div>
                  <div className="font-mono text-[10px] text-slate-500 truncate">
                    {d.email}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
