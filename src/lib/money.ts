/**
 * Money helpers. Backend serialises Decimal as 2-dp JSON strings
 * ("120000.00") to preserve precision. We display them in INR.
 */

export function formatMoney(s: string | number | null | undefined): string {
  if (s === null || s === undefined || s === "") return "₹0.00";
  const n = typeof s === "number" ? s : Number(s);
  if (!Number.isFinite(n)) return "₹0.00";
  return (
    "₹" +
    n.toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

/** Short date display e.g. "2024-08-14". */
export function formatDate(s: string | null | undefined): string {
  if (!s) return "—";
  const head = s.slice(0, 10);
  if (!head) return "—";
  return head;
}

/** Date+time short display, e.g. "2024-08-14 10:32". */
export function formatDateTime(s: string | null | undefined): string {
  if (!s) return "—";
  const head = s.slice(0, 16).replace("T", " ");
  return head || "—";
}

/** Truncate a UUID-like string to its first 8 chars + ellipsis. */
export function truncateId(s: string | null | undefined, n = 8): string {
  if (!s) return "—";
  if (s.length <= n) return s;
  return s.slice(0, n) + "…";
}

/**
 * Convert a money-string ("12345.67") to a JS number for arithmetic.
 * Returns 0 on parse failure.
 */
export function toNumber(s: string | number | null | undefined): number {
  if (s === null || s === undefined || s === "") return 0;
  const n = typeof s === "number" ? s : Number(s);
  return Number.isFinite(n) ? n : 0;
}

/** Percent helper for CSS bars; clamps to [0,100], returns 0 when total≤0. */
export function pct(part: number, total: number): number {
  if (total <= 0) return 0;
  return Math.max(0, Math.min(100, (part / total) * 100));
}
