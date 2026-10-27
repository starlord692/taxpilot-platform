"use client";

import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, ExternalLink, Filter } from "lucide-react";
import { useBusiness } from "@/contexts/business-context";
import { useChartOfAccounts, useGeneralLedger } from "../hooks/use-accounting";
import { formatCurrency, formatDate } from "../utils/accounting-format";

export function GeneralLedgerTable() {
  const { activeBusinessId } = useBusiness();
  const searchParams = useSearchParams();

  const initialAccountId = searchParams.get("account_id") || "";
  const [selectedAccountId, setSelectedAccountId] = useState<string>(initialAccountId);
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [sourceModule, setSourceModule] = useState<string>("");
  const [page, setPage] = useState<number>(1);
  const pageSize = 20;

  // Load accounts for the account filter dropdown
  const { data: accountsData } = useChartOfAccounts(activeBusinessId, { is_active: true });
  const accounts = accountsData?.data ?? [];

  const isSingleAccount = Boolean(selectedAccountId);

  const { data, isLoading, isError, refetch } = useGeneralLedger(activeBusinessId, {
    account_id: selectedAccountId || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    source_module: sourceModule || undefined,
    page,
    size: pageSize,
  });

  const entries = data?.data ?? [];
  const meta = data?.meta ?? { page: 1, size: pageSize, total: 0, pages: 1 };

  if (!activeBusinessId) {
    return (
      <div className="rounded-xl border border-dashed p-8 text-center">
        <p className="text-muted-foreground">Select a business to inspect the General Ledger.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters Bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-4 text-sm">
        <div className="flex items-center gap-1.5 text-muted-foreground font-medium text-xs uppercase tracking-wide">
          <Filter className="size-3.5" /> Filters:
        </div>

        {/* Account Selector */}
        <select
          value={selectedAccountId}
          onChange={(e) => {
            setSelectedAccountId(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">All Accounts</option>
          {accounts.map((acc) => (
            <option key={acc.id} value={acc.id}>
              {acc.account_code} — {acc.account_name} ({acc.category_name})
            </option>
          ))}
        </select>

        {/* Date From */}
        <div className="flex items-center gap-1.5">
          <label className="text-xs text-muted-foreground">From:</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-input bg-background px-2.5 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        {/* Date To */}
        <div className="flex items-center gap-1.5">
          <label className="text-xs text-muted-foreground">To:</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-input bg-background px-2.5 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        {/* Source Module */}
        <select
          value={sourceModule}
          onChange={(e) => {
            setSourceModule(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-input bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">All Source Modules</option>
          <option value="sales">Sales</option>
          <option value="purchases">Purchases</option>
          <option value="expenses">Expenses</option>
        </select>

        {(selectedAccountId || dateFrom || dateTo || sourceModule) && (
          <button
            onClick={() => {
              setSelectedAccountId("");
              setDateFrom("");
              setDateTo("");
              setSourceModule("");
              setPage(1);
            }}
            className="text-xs text-muted-foreground hover:text-foreground underline ml-auto"
          >
            Clear Filters
          </button>
        )}
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
          <p className="text-sm font-medium text-destructive">Failed to load General Ledger entries.</p>
          <button
            onClick={() => void refetch()}
            className="mt-3 rounded-lg bg-primary px-4 py-2 text-xs font-medium text-primary-foreground"
          >
            Retry
          </button>
        </div>
      ) : entries.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center">
          <p className="text-sm font-medium">No ledger entries recorded</p>
          <p className="mt-1 text-xs text-muted-foreground">
            No General Ledger entries match the selected filters or date range.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-muted/40 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Journal No.</th>
                  <th className="px-4 py-3">Account</th>
                  <th className="px-4 py-3">Description</th>
                  <th className="px-4 py-3 text-right">Debit</th>
                  <th className="px-4 py-3 text-right">Credit</th>
                  {isSingleAccount && <th className="px-4 py-3 text-right">Running Balance</th>}
                  <th className="px-4 py-3 text-center">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {entries.map((entry) => (
                  <tr key={entry.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs whitespace-nowrap">
                      {formatDate(entry.transaction_date)}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs font-medium">
                      {entry.journal_number}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-xs">
                        <span className="font-mono text-muted-foreground mr-1.5">{entry.account_code}</span>
                        {entry.account_name}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground max-w-xs truncate">
                      {entry.description || "-"}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-medium tabular-nums">
                      {Number(entry.debit) > 0 ? formatCurrency(entry.debit) : "-"}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-medium tabular-nums">
                      {Number(entry.credit) > 0 ? formatCurrency(entry.credit) : "-"}
                    </td>
                    {isSingleAccount && (
                      <td className="px-4 py-3 text-right font-mono font-semibold tabular-nums text-primary">
                        {formatCurrency(entry.running_balance)}
                      </td>
                    )}
                    <td className="px-4 py-3 text-center">
                      {entry.source_document_url ? (
                        <Link
                          href={entry.source_document_url}
                          className="inline-flex items-center gap-1 rounded bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground hover:bg-secondary/80 transition-colors"
                        >
                          <span className="capitalize">{entry.source_entity?.replace("_", " ")}</span>
                          <ExternalLink className="size-2.5" />
                        </Link>
                      ) : (
                        <span className="text-xs text-muted-foreground">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
            <p>
              Showing {(meta.page - 1) * meta.size + 1}–{Math.min(meta.page * meta.size, meta.total)} of{" "}
              {meta.total} entries
            </p>
            <div className="flex items-center gap-2">
              <button
                disabled={meta.page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 font-medium hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ArrowLeft className="size-3" /> Previous
              </button>
              <span className="px-2 font-mono">
                Page {meta.page} of {Math.max(1, meta.pages)}
              </span>
              <button
                disabled={meta.page >= meta.pages}
                onClick={() => setPage((p) => p + 1)}
                className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 font-medium hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Next <ArrowRight className="size-3" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
