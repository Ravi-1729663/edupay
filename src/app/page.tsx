"use client";

import * as React from "react";
import { GraduationCap } from "lucide-react";

import { LoginCard } from "@/components/edupay/login-card";
import { Dashboard } from "@/components/edupay/dashboard";
import { Footer } from "@/components/edupay/footer";
import {
  ApiError,
  apiFetch,
  clearToken,
  type User,
} from "@/lib/api";

/**
 * EduPay Package A — single-page application.
 *
 * The whole app lives at `/`. There is no router — auth state + role
 * drives which view renders.
 */
export default function Home() {
  const [user, setUser] = React.useState<User | null>(null);
  // Boot: don't flash the login card while we rehydrate a stored token.
  const [booting, setBooting] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    const tok =
      typeof window !== "undefined"
        ? localStorage.getItem("edupay_token")
        : null;
    if (!tok) {
      setBooting(false);
      return;
    }
    apiFetch<User>("/auth/me")
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch((e) => {
        if (cancelled) return;
        // Stale token → drop it & let the user re-login.
        clearToken();
        if (e instanceof ApiError) {
          // Quiet — typical on session expiry.
          console.info("auth/me failed", e.code, e.message);
        }
      })
      .finally(() => !cancelled && setBooting(false));
    return () => {
      cancelled = true;
    };
  }, []);

  if (booting) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50">
        <div className="size-12 rounded-xl bg-emerald-600/10 border border-emerald-200 flex items-center justify-center animate-pulse">
          <GraduationCap className="size-6 text-emerald-700" />
        </div>
        <p className="mt-3 text-sm text-slate-500">Loading EduPay…</p>
        <Footer />
      </div>
    );
  }

  return (
    <>
      {user ? (
        <Dashboard user={user} onSignOut={() => setUser(null)} />
      ) : (
        <div className="min-h-screen flex flex-col">
          <LoginCard onSignedIn={(u) => setUser(u)} />
          <Footer />
        </div>
      )}
    </>
  );
}
