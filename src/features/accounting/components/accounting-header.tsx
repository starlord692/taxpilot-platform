"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, FileSpreadsheet, Landmark, Scale } from "lucide-react";

const tabs = [
  {
    name: "Chart of Accounts",
    href: "/accounting/chart-of-accounts",
    icon: BookOpen,
  },
  {
    name: "General Ledger",
    href: "/accounting/general-ledger",
    icon: FileSpreadsheet,
  },
  {
    name: "Trial Balance",
    href: "/accounting/trial-balance",
    icon: Scale,
  },
];

export function AccountingHeader() {
  const pathname = usePathname();

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Landmark className="size-6 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight">Accounting</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Read-only financial records and double-entry inspection certified by the system of record.
          </p>
        </div>
      </div>

      <div className="flex border-b border-border">
        {tabs.map((tab) => {
          const isActive = pathname === tab.href || (pathname === "/accounting" && tab.href === "/accounting/chart-of-accounts");
          const Icon = tab.icon;
          return (
            <Link
              key={tab.name}
              href={tab.href}
              className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:border-muted hover:text-foreground"
              }`}
            >
              <Icon className="size-4" />
              {tab.name}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
