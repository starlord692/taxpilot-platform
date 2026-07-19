import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/server";
import { salesApi } from "./sales-api";
const base = "http://localhost:8000/api/v1";
beforeAll(() => server.listen({ onUnhandledRequest: "error" })); afterEach(() => server.resetHandlers()); afterAll(() => server.close());
describe("sales API integration", () => {
  it("sends only verified customer-list parameters", async () => { server.use(http.get(`${base}/sales/customers`, ({ request }) => { const entries = [...new URL(request.url).searchParams.entries()]; expect(entries).toEqual([["business_id", "b1"], ["page", "2"], ["page_size", "20"]]); return HttpResponse.json({ success: true, message: "ok", data: [], meta: { page: 2, size: 20, total: 0, pages: 0 } }); })); await expect(salesApi.customers("b1", 2, 20)).resolves.toMatchObject({ data: [] }); });
  it("uses verified invoice detail path without query parameters", async () => { server.use(http.get(`${base}/sales/invoices/i1`, ({ request }) => { expect(new URL(request.url).search).toBe(""); return HttpResponse.json({ success: true, message: "ok", data: { id: "i1", business_id: "b1" } }); })); await expect(salesApi.invoice("i1")).resolves.toMatchObject({ id: "i1" }); });
});
