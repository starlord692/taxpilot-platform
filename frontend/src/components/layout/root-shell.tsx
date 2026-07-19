"use client";
import { usePathname } from "next/navigation";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { AppShell } from "./app-shell";
const publicRoutes = ["/login", "/register", "/forgot-password", "/session-expired", "/unauthorized"];
export function RootShell({ children }: { children: React.ReactNode }) { const pathname = usePathname(); if (publicRoutes.some((route) => pathname.startsWith(route))) return children; return <ProtectedRoute><AppShell>{children}</AppShell></ProtectedRoute>; }
