"use client";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { AuthLoadingScreen } from "./auth-loading-screen";
export function ProtectedRoute({ children }: { children: React.ReactNode }) { const { status } = useAuth(); const router = useRouter(); const pathname = usePathname(); useEffect(() => { if (status === "anonymous") router.replace(`/login?next=${encodeURIComponent(pathname)}`); if (status === "expired") router.replace("/session-expired"); }, [status, router, pathname]); if (status !== "authenticated") return <AuthLoadingScreen />; return children; }
