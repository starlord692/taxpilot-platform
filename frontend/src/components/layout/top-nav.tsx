"use client";
import { Menu, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { UserMenu } from "./user-menu";
export function TopNav({ onMenu }: { onMenu: () => void }) { const { resolvedTheme, setTheme } = useTheme(); return <header className="sticky top-0 z-30 flex h-14 items-center border-b bg-background/85 px-4 backdrop-blur-xl sm:px-6"><Button variant="ghost" size="icon" className="mr-2 lg:hidden" onClick={onMenu} aria-label="Open navigation"><Menu /></Button><div><p className="text-sm font-medium">Workspace</p><p className="hidden text-xs text-muted-foreground sm:block">Tax operations platform</p></div><div className="ml-auto flex items-center gap-2"><Button variant="ghost" size="icon" onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")} aria-label="Toggle color theme"><Sun className="hidden size-4 dark:block" /><Moon className="size-4 dark:hidden" /></Button><UserMenu /></div></header>; }
