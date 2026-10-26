"use client";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import { AuthProvider } from "@/contexts/auth-context";
import { BusinessProvider } from "@/contexts/business-context";
import { QueryProvider } from "./query-provider";
export function AppProviders({ children }: { children: React.ReactNode }) { return <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange><QueryProvider><AuthProvider><BusinessProvider>{children}</BusinessProvider><Toaster richColors closeButton position="bottom-right" /></AuthProvider></QueryProvider></ThemeProvider>; }
