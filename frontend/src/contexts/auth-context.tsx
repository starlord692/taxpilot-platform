"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { authApi } from "@/features/auth/api/auth-api";
import { authQueryKeys } from "@/features/auth/api/auth-query-keys";
import type { AuthStatus, CurrentUser, LoginInput, RegisterInput } from "@/features/auth/types/auth.types";
import { AUTH_EXPIRED_EVENT, AUTH_FORBIDDEN_EVENT } from "@/lib/api/client";
import { clearSession, getSession, setSession } from "@/lib/auth/session-storage";
import { getExpiresAt } from "@/lib/auth/token-expiry";
import { isPreviewMode } from "@/lib/env";

const previewUser: CurrentUser = { id: "preview-user", email: "preview@taxpilot.local", first_name: "Preview", last_name: "User", display_name: "Preview User", status: "active", last_login_at: null, failed_login_attempts: 0, locked_until: null, roles: ["viewer"], permissions: [] };

interface AuthContextValue { status: AuthStatus; user: CurrentUser | null; isAuthenticated: boolean; login: (input: LoginInput) => Promise<void>; register: (input: RegisterInput) => Promise<CurrentUser>; logout: (reason?: "manual" | "expired") => void; revalidateSession: () => Promise<void>; }
const AuthContext = createContext<AuthContextValue | null>(null);
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("initializing"); const [user, setUser] = useState<CurrentUser | null>(null); const queryClient = useQueryClient(); const router = useRouter();
  const reset = useCallback((next: AuthStatus) => { clearSession(); setUser(null); setStatus(next); queryClient.removeQueries({ queryKey: authQueryKeys.all }); }, [queryClient]);
  const revalidateSession = useCallback(async () => { if (isPreviewMode) { setUser(previewUser); setStatus("authenticated"); return; } const stored = getSession(); if (!stored) { setStatus("anonymous"); return; } try { const profile = await queryClient.fetchQuery({ queryKey: authQueryKeys.me(), queryFn: authApi.me, staleTime: 60_000 }); setUser({ ...profile, roles: stored.user.roles, permissions: stored.user.permissions }); setStatus("authenticated"); } catch { reset("expired"); } }, [queryClient, reset]);
  useEffect(() => { void revalidateSession(); }, [revalidateSession]);
  useEffect(() => { const expired = () => { reset("expired"); router.replace("/session-expired"); }; const forbidden = () => router.replace("/unauthorized"); window.addEventListener(AUTH_EXPIRED_EVENT, expired); window.addEventListener(AUTH_FORBIDDEN_EVENT, forbidden); return () => { window.removeEventListener(AUTH_EXPIRED_EVENT, expired); window.removeEventListener(AUTH_FORBIDDEN_EVENT, forbidden); }; }, [reset, router]);
  const login = useCallback(async (input: LoginInput) => { setStatus("authenticating"); try { const response = await authApi.login(input); setSession({ accessToken: response.access_token, expiresAt: getExpiresAt(response.expires_in), user: response.user }); const profile = await authApi.me(); queryClient.setQueryData(authQueryKeys.me(), profile); setUser({ ...profile, roles: response.user.roles, permissions: response.user.permissions }); setStatus("authenticated"); } catch (error) { reset("anonymous"); throw error; } }, [queryClient, reset]);
  const register = useCallback((input: RegisterInput) => authApi.register(input), []);
  const logout = useCallback((reason: "manual" | "expired" = "manual") => { reset(reason === "expired" ? "expired" : "anonymous"); router.replace(reason === "expired" ? "/session-expired" : "/login"); }, [reset, router]);
  const value = useMemo(() => ({ status, user, isAuthenticated: status === "authenticated", login, register, logout, revalidateSession }), [status, user, login, register, logout, revalidateSession]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth() { const context = useContext(AuthContext); if (!context) throw new Error("useAuth must be used within AuthProvider"); return context; }
