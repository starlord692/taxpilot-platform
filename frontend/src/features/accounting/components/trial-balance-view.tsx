"use client";

import { useState } from "react";
import { AlertCircle, CheckCircle2, Info } from "lucide-react";
import { useBusiness } from "@/contexts/business-context";
import { useTrialBalance } from "../hooks/use-accounting";
import { formatCurrency } from "../utils/accounting-format";

export function TrialBalanceView() {
  const { activeBusinessId } = useBusiness();
  const [asOfDate, setAsOfDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [includeZeroBalances, setIncludeZeroBalances] = useState<boolean>(false);

  const { data, isLoading, isError, refetch } = useTrialBalance(activeBusinessId, {
    as_of_date: asOfDate || undefined,
    include_zero_balances: includeZeroBalances,
  });

  const tb = data?.data;
  const accounts = tb?.accounts ?? [];

  if (!activeBusinessId) {
    return (
      <div className="rounded-xl border border-dashed p-8 text-center">
        <p className="text-muted-foreground">Select a business to inspect the Trial Balance.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Reconciliation Banner */}
      {tb && (
        <div className="space-y-3">
          {tb.is_balanced ? (
            <div className="flex items-start gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-4 text-emerald-800 dark:text-emerald-300">
              <CheckCircle2 className="size-5 shrink-0 mt-0.5 text-emerald-600 dark:text-emerald-400" />
              <div className="text-sm">
                <p className="font-semibold">
                  LEDGER RECONCILIATION: Total Debits equal Total Credits (
                  {formatCurrency(tb.total_debit)} == {formatCurrency(tb.total_credit)})
                </p>
                <p className="text-xs opacity-90 mt-0.5">
                  Net discrepancy is ₹0.00 under defined double-entry ledger calculation.
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-start gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-rose-800 dark:text-rose-300">
              <AlertCircle className="size-5 shrink-0 mt-0.5 text-rose-600 dark:text-rose-400" />
              <div className="text-sm">
                <p className="font-semibold">
                  (!) CRITICAL INVARIANT WARNING: Trial Balance is out of balance by{" "}
                  {formatCurrency(tb.discrepancy)}
                </p>
                <p className="text-xs opacity-90 mt-0.5">
                  Total Debits: {formatCurrency(tb.total_debit)} | Total Credits:{" "}
                  {formatCurrency(tb.total_credit)}. Contact technical support.
                </p>
              </div>
            </div>
          )}

          {/* Reporting Disclosure Banner */}
          {(!tb.opening_balances_present || !tb.fiscal_period_closed) && (
            <div className="flex items-start gap-3 rounded-xl border border-amber-500/20 bg-amber-500/10 p-4 text-amber-900 dark:text-amber-200">
              <Info className="size-5 shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
              <div className="text-xs space-y-1">
                <p className="font-semibold text-sm">
                  REPORTING DISCLOSURE: Cumulative Ledger-Derived Balances
                </p>
                <p>
                  Balances reflect cumulative ledger entries recorded in TaxPilot from inception to cutoff date.
                  Pre-system opening balances and annual fiscal-year closing entries are not present in the system.
                  Revenue and expense accounts reflect cumulative activity rather than annual reset.
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium">As-of Date:</label>
            <input
              type="date"
              value={asOfDate}
              onChange={(e) => setAsOfDate(e.target.value)}
              className="rounded-lg border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none">
            <input
              type="checkbox"
              checked={includeZeroBalances}
              onChange={(e) => setIncludeZeroBalances(e.target.checked)}
              className="size-4 rounded border-input text-primary focus:ring-primary"
            />
            Include Zero-Balance Accounts
          </label>
        </div>

        <button
          onClick={() => window.print()}
          className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors"
        >
          Print / Export
        </button>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="space-y-2">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-12 w-full animate-pulse rounded-lg bg-muted/50" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-xl border border-destructive/20 bg-destructive/10 p-6 text-center">
          <p className="text-sm font-medium text-destructive">Failed to generate Trial Balance.</p>
          <button
            onClick={() => void refetch()}
            className="mt-3 rounded-lg bg-primary px-4 py-2 text-xs font-medium text-primary-foreground"
          >
            Retry
          </button>
        </div>
      ) : accounts.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center">
          <p className="text-sm font-medium">No account balances</p>
          <p className="mt-1 text-xs text-muted-foreground">
            No accounts have non-zero recorded balances as of {asOfDate}.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-muted/40 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-3">Code</th>
                <th className="px-4 py-3">Account Name</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3 text-right">Debit (₹)</th>
                <th className="px-4 py-3 text-right">Credit (₹)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {accounts.map((row) => (
                <tr key={row.account_id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-2.5 font-mono font-medium text-xs">{row.account_code}</td>
                  <td className="px-4 py-2.5 font-medium">
                    <span>{row.account_name}</span>
                    <span className="ml-2 text-xs text-muted-foreground font-normal">
                      ({row.account_type})
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-muted-foreground">{row.account_category}</td>
                  <td className="px-4 py-2.5 text-right font-mono tabular-nums font-medium">
                    {Number(row.debit) > 0 ? formatCurrency(row.debit) : "-"}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono tabular-nums font-medium">
                    {Number(row.credit) > 0 ? formatCurrency(row.credit) : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
            {tb && (
              <tfoot className="border-t-2 border-border bg-muted/30 text-xs font-mono font-bold">
                <tr>
                  <td colSpan={3} className="px-4 py-3 uppercase tracking-wide">
                    TOTALS
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-sm">
                    {formatCurrency(tb.total_debit)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-sm">
                    {formatCurrency(tb.total_credit)}
                  </td>
                </tr>
                <tr className="border-t border-border/50 text-muted-foreground">
                  <td colSpan={3} className="px-4 py-2 font-normal">
                    NET DISCREPANCY
                  </td>
                  <td colSpan={2} className="px-4 py-2 text-right tabular-nums">
                    {formatCurrency(tb.discrepancy)}
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      )}

      {/* Disclaimer */}
      <div className="rounded-lg border border-border/60 bg-muted/20 p-4 text-xs text-muted-foreground leading-relaxed">
        <p className="font-semibold text-foreground/80 mb-1">Audit & Certification Boundaries</p>
        <p>
          Ledger reconciliation confirms mathematical equality between total debits and total credits of recorded
          transactions. It does not prove the completeness of unrecorded external transactions, the correctness of
          business classification, or statutory compliance with annual filing requirements.
        </p>
      </div>
    </div>
  );
}
