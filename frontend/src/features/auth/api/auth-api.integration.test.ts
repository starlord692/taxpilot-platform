import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/server";
import { authApi } from "./auth-api";
import { clearSession, setSession } from "@/lib/auth/session-storage";
const base = "http://localhost:8000/api/v1";
const profile = { id: "u1", email: "owner@example.com", first_name: "Jane", last_name: "Doe", display_name: "Jane Doe", status: "active" as const, last_login_at: null, failed_login_attempts: 0, locked_until: null };
beforeAll(() => server.listen({ onUnhandledRequest: "error" })); afterEach(() => { server.resetHandlers(); clearSession(); }); afterAll(() => server.close());
describe("authentication API integration", () => {
  it("creates a session through the token-issuing endpoint", async () => { server.use(http.post(`${base}/identity/session`, async ({ request }) => { expect(await request.json()).toEqual({ email: "owner@example.com", password: "StrongPass123!" }); return HttpResponse.json({ success: true, message: "ok", data: { access_token: "jwt", refresh_token: "opaque", token_type: "Bearer", expires_in: 900, user: { id: "u1", email: "owner@example.com", roles: ["member"], permissions: [] } } }); })); const result = await authApi.login({ email: "owner@example.com", password: "StrongPass123!" }); expect(result.access_token).toBe("jwt"); });
  it("registers using only the existing registration endpoint", async () => { server.use(http.post(`${base}/identity/register`, () => HttpResponse.json({ success: true, message: "created", data: profile }, { status: 201 }))); await expect(authApi.register({ email: profile.email, first_name: "Jane", last_name: "Doe", password: "StrongPass123!" })).resolves.toEqual(profile); });
  it("adds the bearer token when loading the current user", async () => { setSession({ accessToken: "jwt", expiresAt: Date.now() + 60_000, user: { id: "u1", email: profile.email, roles: [], permissions: [] } }); server.use(http.get(`${base}/identity/me`, ({ request }) => { expect(request.headers.get("authorization")).toBe("Bearer jwt"); return HttpResponse.json(profile); })); await expect(authApi.me()).resolves.toEqual(profile); });
});
