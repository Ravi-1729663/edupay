"use client";

import * as React from "react";

/** Debounce a fast-changing value (e.g. a search box). */
export function useDebounced<T>(value: T, delayMs = 300): T {
  const [deb, setDeb] = React.useState(value);
  React.useEffect(() => {
    const t = setTimeout(() => setDeb(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return deb;
}

/** Abortable async fetch hook for a single API call. */
export function useAsync<T>(
  fn: () => Promise<T>,
  deps: React.DependencyList,
): {
  data: T | null;
  loading: boolean;
  error: Error | null;
  reload: () => void;
  setData: (updater: T | null | ((prev: T | null) => T | null)) => void;
} {
  const [data, setData] = React.useState<T | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<Error | null>(null);
  const [seq, setSeq] = React.useState(0);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fn()
      .then((v) => {
        if (!cancelled) setData(v);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e : new Error(String(e)));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [...deps, seq]);

  const reload = React.useCallback(() => setSeq((n) => n + 1), []);
  const setDataWrapper = React.useCallback(
    (updater: T | null | ((prev: T | null) => T | null)) => {
      setData((prev) =>
        typeof updater === "function"
          ? (updater as (p: T | null) => T | null)(prev)
          : updater,
      );
    },
    [],
  );

  return { data, loading, error, reload, setData: setDataWrapper };
}
