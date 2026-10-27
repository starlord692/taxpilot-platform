export type AuthStatus = "initializing" | "anonymous" | "authenticating" | "authenticated" | "expired";
export interface SessionUser { id: string; email: string; roles: string[]; permissions: string[]; }
export interface CurrentUser { id: string; email: string; first_name: string; last_name: string; display_name: string; status: "pending" | "active" | "disabled"; last_login_at: string | null; failed_login_attempts: number; locked_until: string | null; roles?: string[]; permissions?: string[]; }
export interface LoginInput { email: string; password: string; }
export interface RegisterInput { email: string; first_name: string; last_name: string; display_name?: string; password: string; }
export interface SessionResponse { access_token: string; refresh_token: string; token_type: string; expires_in: number; user: SessionUser; }
export interface StoredSession { accessToken: string; expiresAt: number; user: SessionUser; }
export interface ApiEnvelope<T> { success: boolean; message: string; data: T; }
