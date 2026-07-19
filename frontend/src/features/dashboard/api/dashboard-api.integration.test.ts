import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/server";
import { dashboardApi } from "./dashboard-api";
const base = "http://localhost:8000/api/v1";
const paginated = <T,>(data: T[]) => ({ success: true, message: "ok", data, meta: { page: 1, size: 5, total: data.length, pages: 1 } });
beforeAll(() => server.listen({ onUnhandledRequest: "error" })); afterEach(() => server.resetHandlers()); afterAll(() => server.close());
describe("dashboard API integration", () => { it("requests sorted expense and purchase activity", async () => { server.use(http.get(`${base}/expenses`, ({ request }) => { expect(new URL(request.url).searchParams.get("sort")).toBe("-expense_date"); return HttpResponse.json(paginated([])); }), http.get(`${base}/purchases`, ({ request }) => { expect(new URL(request.url).searchParams.get("sort")).toBe("-invoice_date"); return HttpResponse.json(paginated([])); })); await Promise.all([dashboardApi.expenses("b1"), dashboardApi.purchases("b1")]); }); it("uses the existing health endpoint", async () => { server.use(http.get(`${base}/health`, () => HttpResponse.json({ success: true, message: "healthy", data: { status: "UP", version: "1.0.0", environment: "test" } }))); expect((await dashboardApi.health()).data.status).toBe("UP"); }); });
