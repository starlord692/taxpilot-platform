import type { StoredSession } from "@/features/auth/types/auth.types";
import { isSessionExpired } from "./token-expiry";
const SESSION_KEY = "taxpilot.auth.session.v1";
let memorySession: StoredSession | null = null;
function storage() { return typeof window === "undefined" ? null : window.sessionStorage; }
export function getSession(): StoredSession | null { if (memorySession) { if (isSessionExpired(memorySession.expiresAt)) { clearSession(); return null; } return memorySession; } const raw = storage()?.getItem(SESSION_KEY); if (!raw) return null; try { const parsed = JSON.parse(raw) as StoredSession; if (!parsed.accessToken || !parsed.user?.id || isSessionExpired(parsed.expiresAt)) { clearSession(); return null; } memorySession = parsed; return parsed; } catch { clearSession(); return null; } }
export function setSession(session: StoredSession) { memorySession = session; storage()?.setItem(SESSION_KEY, JSON.stringify(session)); }
export function clearSession() { memorySession = null; storage()?.removeItem(SESSION_KEY); }
export function getAccessToken() { const session = getSession(); return session && !isSessionExpired(session.expiresAt) ? session.accessToken : null; }
