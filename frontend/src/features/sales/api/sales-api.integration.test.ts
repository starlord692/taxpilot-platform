import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/server";
import { salesApi } from "./sales-api";

const base = "http://localhost:8000/api/v1";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("sales API integration", () => {
  it("sends only verified customer-list parameters", async () => {
    server.use(
      http.get(`${base}/sales/customers`, ({ request }) => {
        const entries = [...new URL(request.url).searchParams.entries()];
        expect(entries).toEqual([
          ["business_id", "b1"],
          ["page", "2"],
          ["page_size", "20"],
        ]);
        return HttpResponse.json({
          success: true,
          message: "ok",
          data: [],
          meta: { page: 2, size: 20, total: 0, pages: 0 },
        });
      })
    );
    await expect(salesApi.customers("b1", 2, 20)).resolves.toMatchObject({ data: [] });
  });

  it("uses verified invoice detail path without query parameters", async () => {
    server.use(
      http.get(`${base}/sales/invoices/i1`, ({ request }) => {
        expect(new URL(request.url).search).toBe("");
        return HttpResponse.json({
          success: true,
          message: "ok",
          data: { id: "i1", business_id: "b1" },
        });
      })
    );
    await expect(salesApi.invoice("i1")).resolves.toMatchObject({ id: "i1" });
  });

  it("posts invoice creation payload to /sales/invoices and returns data", async () => {
    const payload = {
      business_id: "b1",
      customer_id: "c1",
      invoice_number: "INV-0001",
      invoice_date: "2026-04-01",
      due_date: "2026-04-30",
      status: "draft" as const,
      subtotal: 1000,
      discount_amount: 50,
      taxable_amount: 950,
      tax_amount: 171,
      total_amount: 1121,
      notes: "Test invoice",
      lines: [
        {
          description: "Consulting",
          quantity: 2,
          unit_price: 500,
          discount: 50,
          tax_rate: 18,
          cgst_amount: 85.5,
          sgst_amount: 85.5,
          igst_amount: 0,
          cess_amount: 0,
          line_total: 1121,
        },
      ],
    };
    server.use(
      http.post(`${base}/sales/invoices`, async ({ request }) => {
        const body = await request.json();
        expect(body).toEqual(payload);
        return HttpResponse.json({
          success: true,
          message: "Invoice created successfully",
          data: {
            id: "inv-123",
            ...payload,
            payments: [],
          },
        });
      })
    );
    const result = await salesApi.createInvoice(payload);
    expect(result).toMatchObject({
      id: "inv-123",
      invoice_number: "INV-0001",
      status: "draft",
    });
  });

  it("posts to /sales/invoices/:id/issue without body and returns issued invoice", async () => {
    server.use(
      http.post(`${base}/sales/invoices/inv-123/issue`, async ({ request }) => {
        expect(new URL(request.url).search).toBe("");
        const bodyText = await request.text();
        expect(bodyText === "" || bodyText === "{}" || bodyText === "null").toBe(true);
        return HttpResponse.json({
          success: true,
          message: "Invoice issued successfully",
          data: {
            id: "inv-123",
            business_id: "b1",
            invoice_number: "INV-0001",
            status: "issued",
            total_amount: 1121,
            lines: [],
            payments: [],
          },
        });
      })
    );

    const result = await salesApi.issueInvoice("inv-123");
    expect(result).toMatchObject({
      id: "inv-123",
      status: "issued",
      invoice_number: "INV-0001",
    });
  });

  it("posts to /sales/invoices/:id/cancel without body and returns cancelled invoice", async () => {
    server.use(
      http.post(`${base}/sales/invoices/inv-123/cancel`, async ({ request }) => {
        expect(new URL(request.url).search).toBe("");
        const bodyText = await request.text();
        expect(bodyText === "" || bodyText === "{}" || bodyText === "null").toBe(true);
        return HttpResponse.json({
          success: true,
          message: "Invoice cancelled successfully",
          data: {
            id: "inv-123",
            business_id: "b1",
            invoice_number: "INV-0001",
            status: "cancelled",
            total_amount: 1121,
            lines: [],
            payments: [],
          },
        });
      })
    );

    const result = await salesApi.cancelInvoice("inv-123");
    expect(result).toMatchObject({
      id: "inv-123",
      status: "cancelled",
      invoice_number: "INV-0001",
    });
  });
});
