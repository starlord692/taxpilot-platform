"use client";

import { Bell, Menu, Moon, Search, Sparkles, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { BusinessSwitcher } from "@/components/business/business-switcher";
import { Button } from "@/components/ui/button";
import { UserMenu } from "./user-menu";

export function TopNav({ onMenu }: { onMenu: () => void }) {
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <header className="sticky top-0 z-30 flex h-[3.75rem] items-center gap-2 border-b bg-background/90 px-3 backdrop-blur-xl sm:px-5">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2">Skip to content</a>
      <Button variant="ghost" size="icon" className="lg:hidden" onClick={onMenu} aria-label="Open navigation"><Menu /></Button>
      <div className="hidden w-56 lg:block"><BusinessSwitcher /></div>
      <button type="button" className="flex h-9 min-w-0 flex-1 items-center gap-2 rounded-xl border bg-muted/30 px-3 text-left text-sm text-muted-foreground outline-none hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring sm:max-w-md" aria-label="Global search (coming soon)" disabled>
        <Search className="size-4 shrink-0" /><span className="truncate">Search TaxPilot</span><kbd className="ml-auto hidden rounded border bg-background px-1.5 py-0.5 text-[10px] sm:inline">⌘ K</kbd>
      </button>
      <div className="ml-auto flex items-center gap-1">
        <Button variant="outline" size="sm" className="hidden gap-2 xl:inline-flex" disabled aria-label="AI Assistant coming soon"><Sparkles className="size-4" />AI Assistant</Button>
        <Button variant="ghost" size="icon" disabled aria-label="Notifications coming soon"><Bell className="size-4" /></Button>
        <Button variant="ghost" size="icon" onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")} aria-label="Toggle color theme"><Sun className="hidden size-4 dark:block" /><Moon className="size-4 dark:hidden" /></Button>
        <UserMenu />
      </div>
    </header>
  );
}
