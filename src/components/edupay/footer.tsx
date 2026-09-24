import * as React from "react";

export function Footer() {
  return (
    <footer
      className={
        "mt-auto border-t border-slate-200 bg-slate-50 text-slate-600 " +
        "text-xs py-4 px-4 sm:px-6 lg:px-8"
      }
    >
      <div className="mx-auto max-w-7xl flex flex-col sm:flex-row items-center justify-between gap-2">
        <p>EduPay — Package A scaffold · Financial-grade fee system</p>
        <p className="text-slate-500">
          See <code className="font-mono text-slate-700">/docs</code> for the
          API contract &amp; data model
        </p>
      </div>
    </footer>
  );
}
