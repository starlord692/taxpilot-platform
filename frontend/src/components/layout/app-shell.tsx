"use client";
import { useState } from "react";
import { Sidebar } from "./sidebar";
import { TopNav } from "./top-nav";
export function AppShell({ children }: { children: React.ReactNode }) { const [mobileOpen, setMobileOpen] = useState(false); return <div className="min-h-screen bg-background"><Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} /><div className="lg:pl-64"><TopNav onMenu={() => setMobileOpen(true)} /><main className="min-h-[calc(100vh-3.5rem)]">{children}</main></div></div>; }
