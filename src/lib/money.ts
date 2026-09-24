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
