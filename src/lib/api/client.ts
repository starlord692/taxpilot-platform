import axios from "axios";
import { env } from "@/lib/env";
import { getAccessToken } from "@/lib/auth/session-storage";
import { normalizeApiError } from "./errors";
export const AUTH_EXPIRED_EVENT = "taxpilot:auth-expired";
export const AUTH_FORBIDDEN_EVENT = "taxpilot:auth-forbidden";
export const apiClient = axios.create({ baseURL: env.NEXT_PUBLIC_API_URL, timeout: 15_000, headers: { "Content-Type": "application/json" } });
apiClient.interceptors.request.use((config) => { const token = getAccessToken(); if (token && !config.headers.Authorization) config.headers.Authorization = `Bearer ${token}`; return config; });
apiClient.interceptors.response.use((response) => response, (error) => { const normalized = normalizeApiError(error); const status = axios.isAxiosError(error) ? error.response?.status : undefined; const path = axios.isAxiosError(error) ? String(error.config?.url ?? "") : ""; const isAuthRequest = path.includes("/identity/session") || path.includes("/identity/register"); if (typeof window !== "undefined" && status === 401 && !isAuthRequest) window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT)); if (typeof window !== "undefined" && status === 403 && !isAuthRequest) window.dispatchEvent(new CustomEvent(AUTH_FORBIDDEN_EVENT)); return Promise.reject(normalized); });
