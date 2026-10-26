"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, FileSpreadsheet, Landmark, Scale } from "lucide-react";
import { useBusiness } from "@/contexts/business-context";
import { BusinessRouteShell } from "@/components/business/business-route-shell";
import { BusinessSwitcher } from "@/components/business/business-switcher";
import { cn } from "@/lib/utils";

const links = [
  { href: "/accounting/chart-of-accounts", label: "Chart of Accounts", icon: BookOpen },
  { href: "/accounting/general-ledger", label: "General Ledger", icon: FileSpreadsheet },
  { href: "/accounting/trial-balance", label: "Trial Balance", icon: Scale },
];

export function AccountingShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { businesses } = useBusiness();

  return (
    <BusinessRouteShell>
      <div className="space-y-6">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Landmark className="size-5 text-primary" />
              <p className="text-sm font-medium text-primary">Accounting</p>
            </div>
            <h1 className="text-2xl font-semibold tracking-tight">Financial System of Record</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Deterministic double-entry inspection, chart of accounts, and ledger reconciliation.
            </p>
          </div>
          {businesses.length > 1 && (
            <div className="w-full sm:w-72">
              <BusinessSwitcher />
            </div>
          )}
        </header>

        <nav aria-label="Accounting sections" className="flex gap-1 overflow-x-auto border-b">
          {links.map(({ href, label, icon: Icon }) => {
            const active =
              path === href ||
              (path === "/accounting" && href === "/accounting/chart-of-accounts");
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="size-4" />
                {label}
              </Link>
            );
          })}
        </nav>

        {children}
      </div>
    </BusinessRouteShell>
  );
}
