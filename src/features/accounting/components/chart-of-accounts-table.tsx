"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Search } from "lucide-react";
import { useBusiness } from "@/contexts/business-context";
import { useChartOfAccounts } from "../hooks/use-accounting";
import { formatCurrency } from "../utils/accounting-format";

export function ChartOfAccountsTable() {
  const { activeBusinessId } = useBusiness();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("true");

  const isActiveParam = statusFilter === "" ? undefined : statusFilter === "true";

  const { data, isLoading, isError, refetch } = useChartOfAccounts(activeBusinessId, {
    category: category || undefined,
    is_active: isActiveParam,
    search: search || undefined,
  });

  const accounts = data?.data ?? [];

  if (!activeBusinessId) {
    return (
      <div className="rounded-xl border border-dashed p-8 text-center">
        <p className="text-muted-foreground">Select a business to inspect the Chart of Accounts.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search code or name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-input bg-background pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="">All Categories</option>
            <option value="Asset">Asset</option>
            <option value="Liability">Liability</option>
            <option value="Equity">Equity</option>
            <option value="Revenue">Revenue</option>
            <option value="Expense">Expense</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="">All Statuses</option>
            <option value="true">Active Only</option>
            <option value="false">Inactive Only</option>
          </select>
        </div>
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
          <p className="text-sm font-medium text-destructive">Failed to load Chart of Accounts.</p>
          <button
            onClick={() => void refetch()}
            className="mt-3 rounded-lg bg-primary px-4 py-2 text-xs font-medium text-primary-foreground"
          >
            Retry
          </button>
        </div>
      ) : accounts.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center">
          <p className="text-sm font-medium">No accounts found</p>
          <p className="mt-1 text-xs text-muted-foreground">
            No chart accounts match the selected filters for this business.
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
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3 text-center">Normal</th>
                <th className="px-4 py-3 text-right">Current Balance</th>
                <th className="px-4 py-3 text-center">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {accounts.map((acc) => (
                <tr key={acc.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-mono font-medium">{acc.account_code}</td>
                  <td className="px-4 py-3 font-medium">
                    <div>
                      <span>{acc.account_name}</span>
                      {acc.description && (
                        <p className="text-xs text-muted-foreground font-normal">{acc.description}</p>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center rounded-md bg-secondary px-2 py-0.5 text-xs font-medium">
                      {acc.category_name}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">{acc.account_type_name}</td>
                  <td className="px-4 py-3 text-center">
                    <span className="text-xs uppercase font-mono text-muted-foreground">{acc.normal_balance}</span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-medium tabular-nums">
                    {formatCurrency(acc.current_balance)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        acc.is_active
                          ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {acc.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/accounting/general-ledger?account_id=${acc.id}`}
                      className="inline-flex items-center gap-1 text-xs text-primary hover:underline font-medium"
                    >
                      View GL <ArrowUpRight className="size-3" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
