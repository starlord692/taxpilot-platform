import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/server";
import { businessApi } from "./business-api";
const base = "http://localhost:8000/api/v1";
beforeAll(() => server.listen({ onUnhandledRequest: "error" })); afterEach(() => server.resetHandlers()); afterAll(() => server.close());
describe("business API integration", () => { it("loads accessible businesses from the verified endpoint", async () => { server.use(http.get(`${base}/businesses/`, ({ request }) => { expect(new URL(request.url).searchParams.get("page_size")).toBe("100"); return HttpResponse.json({ success: true, message: "ok", data: [{ id: "b1", legal_name: "One", trade_name: null, business_type: "company", status: "active" }], meta: { page: 1, size: 100, total: 1, pages: 1 } }); })); expect((await businessApi.list()).data[0].id).toBe("b1"); }); it("loads GST only from the verified registration endpoint", async () => { server.use(http.get(`${base}/gst/registrations`, ({ request }) => { expect(new URL(request.url).searchParams.get("business_id")).toBe("b1"); return HttpResponse.json({ success: true, message: "ok", data: [], meta: { page: 1, size: 20, total: 0, pages: 0 } }); })); await expect(businessApi.gst("b1")).resolves.toMatchObject({ data: [] }); }); });
