"use client";

import { useEffect, useState } from "react";
import { Sidebar } from "./sidebar";
import { TopNav } from "./top-nav";
import { cn } from "@/lib/utils";

const SIDEBAR_KEY = "taxpilot-sidebar-collapsed";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setCollapsed(window.localStorage.getItem(SIDEBAR_KEY) === "true");
  }, []);

  function toggleCollapsed() {
    setCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem(SIDEBAR_KEY, String(next));
      return next;
    });
  }

  return (
    <div className="min-h-screen bg-background">
      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
        onToggleCollapsed={toggleCollapsed}
      />
      <div className={cn("transition-[padding] duration-200 lg:pl-64", collapsed && "lg:pl-20")}>
        <TopNav onMenu={() => setMobileOpen(true)} />
        <main id="main-content" className="min-h-[calc(100vh-3.75rem)]" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
