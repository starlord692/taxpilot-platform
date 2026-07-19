"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronLeft, X } from "lucide-react";
import { activeNavigationHref, navigation } from "@/config/navigation";
import { cn } from "@/lib/utils";
import { BusinessSwitcher } from "@/components/business/business-switcher";

type SidebarProps = {
  collapsed: boolean;
  mobileOpen: boolean;
  onClose: () => void;
  onToggleCollapsed: () => void;
};

export function Sidebar({ collapsed, mobileOpen, onClose, onToggleCollapsed }: SidebarProps) {
  const pathname = usePathname();
  const activeHref = activeNavigationHref(pathname);

  return (
    <>
      <button
        aria-label="Close navigation"
        className={cn("fixed inset-0 z-40 bg-black/40 backdrop-blur-sm transition-opacity lg:hidden", mobileOpen ? "opacity-100" : "pointer-events-none opacity-0")}
        onClick={onClose}
      />
      <aside
        aria-label="Primary"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r bg-card shadow-xl transition-[transform,width] duration-200 lg:translate-x-0 lg:shadow-none",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
          collapsed && "lg:w-20",
        )}
      >
        <div className="flex h-[3.75rem] items-center border-b px-4">
          <Link href="/" className="flex min-w-0 items-center gap-2.5 font-semibold tracking-tight" onClick={onClose}>
            <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-primary text-xs font-bold text-primary-foreground shadow-sm">T</span>
            <span className={cn("truncate transition-opacity", collapsed && "lg:sr-only")}>TaxPilot</span>
          </Link>
          <button className="ml-auto rounded-lg p-2 text-muted-foreground hover:bg-accent lg:hidden" onClick={onClose} aria-label="Close navigation"><X className="size-4" /></button>
        </div>
        <div className={cn("border-b p-3 lg:hidden", !collapsed && "lg:block")}><BusinessSwitcher /></div>
        <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="Main navigation">
          {navigation.map(({ label, href, icon: Icon }) => {
            const active = activeHref === href;
            return (
              <Link
                key={href}
                href={href}
                title={collapsed ? label : undefined}
                aria-current={active ? "page" : undefined}
                onClick={onClose}
                className={cn(
                  "group flex min-h-10 items-center gap-3 rounded-xl px-3 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                  active ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
                  collapsed && "lg:justify-center lg:px-0",
                )}
              >
                <Icon className="size-[18px] shrink-0" aria-hidden="true" />
                <span className={cn("truncate", collapsed && "lg:sr-only")}>{label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="hidden border-t p-3 lg:block">
          <button
            type="button"
            onClick={onToggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex h-9 w-full items-center justify-center gap-2 rounded-lg text-xs font-medium text-muted-foreground outline-none hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ChevronLeft className={cn("size-4 transition-transform", collapsed && "rotate-180")} />
            {!collapsed && "Collapse"}
          </button>
        </div>
      </aside>
    </>
  );
}
