import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/server";
import { accountingApi } from "./accounting-api";

const base = "http://localhost:8000/api/v1";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("accounting API integration", () => {
  it("sends chart-of-accounts parameters correctly", async () => {
    server.use(
      http.get(`${base}/accounting/chart-of-accounts`, ({ request }) => {
        const params = new URL(request.url).searchParams;
        expect(params.get("business_id")).toBe("b1");
        expect(params.get("category")).toBe("Asset");
        return HttpResponse.json({
          success: true,
          message: "ok",
          data: [
            {
              id: "a1",
              account_code: "1000",
              account_name: "Cash",
              category_name: "Asset",
              account_type_name: "Current Asset",
              normal_balance: "debit",
              current_debit: "100.00",
              current_credit: "0.00",
              current_balance: "100.00",
              is_system: true,
              is_active: true,
              parent_account_id: null,
              description: null,
            },
          ],
        });
      })
    );

    const res = await accountingApi.chartOfAccounts("b1", { category: "Asset" });
    expect(res.data).toHaveLength(1);
    expect(res.data[0].account_code).toBe("1000");
  });

  it("sends general-ledger query parameters correctly", async () => {
    server.use(
      http.get(`${base}/accounting/general-ledger`, ({ request }) => {
        const params = new URL(request.url).searchParams;
        expect(params.get("business_id")).toBe("b1");
        expect(params.get("account_id")).toBe("a1");
        expect(params.get("page")).toBe("1");
        expect(params.get("size")).toBe("20");
        return HttpResponse.json({
          success: true,
          message: "ok",
          data: [],
          meta: { page: 1, size: 20, total: 0, pages: 0 },
        });
      })
    );

    const res = await accountingApi.generalLedger("b1", { account_id: "a1", page: 1, size: 20 });
    expect(res.data).toEqual([]);
    expect(res.meta.total).toBe(0);
  });

  it("sends trial-balance query parameters and returns balanced report", async () => {
    server.use(
      http.get(`${base}/accounting/trial-balance`, ({ request }) => {
        const params = new URL(request.url).searchParams;
        expect(params.get("business_id")).toBe("b1");
        expect(params.get("as_of_date")).toBe("2026-10-15");
        return HttpResponse.json({
          success: true,
          message: "ok",
          data: {
            business_id: "b1",
            generated_at: "2026-10-20T21:00:00Z",
            as_of_date: "2026-10-15",
            total_debit: "5000.00",
            total_credit: "5000.00",
            discrepancy: "0.00",
            is_balanced: true,
            historical_mode: "ledger_derived_cumulative",
            opening_balances_present: false,
            fiscal_period_closed: false,
            reporting_limitations: ["Notice"],
            accounts: [],
          },
        });
      })
    );

    const res = await accountingApi.trialBalance("b1", { as_of_date: "2026-10-15" });
    expect(res.data.is_balanced).toBe(true);
    expect(res.data.total_debit).toBe("5000.00");
  });

  it("sends account-detail request and returns account", async () => {
    server.use(
      http.get(`${base}/accounting/chart-of-accounts/:id`, ({ request, params }) => {
        const urlParams = new URL(request.url).searchParams;
        expect(urlParams.get("business_id")).toBe("b1");
        expect(params.id).toBe("acc-123");
        return HttpResponse.json({
          success: true,
          message: "ok",
          data: {
            id: "acc-123",
            account_code: "1000",
            account_name: "Cash in Hand",
            category_name: "Asset",
            account_type_name: "Cash",
            normal_balance: "debit",
            current_debit: "1000.00",
            current_credit: "0.00",
            current_balance: "1000.00",
            is_system: true,
            is_active: true,
            parent_account_id: null,
            description: null,
          },
        });
      })
    );

    const res = await accountingApi.accountDetail("acc-123", "b1");
    expect(res.id).toBe("acc-123");
    expect(res.account_name).toBe("Cash in Hand");
  });

  it("propagates API errors correctly for 400 future date error", async () => {
    server.use(
      http.get(`${base}/accounting/trial-balance`, () => {
        return HttpResponse.json(
          {
            error: {
              code: "accounting.trial_balance_future_date",
              message: "Historical Trial Balance cannot be generated for future dates",
            },
          },
          { status: 400 }
        );
      })
    );

    await expect(
      accountingApi.trialBalance("b1", { as_of_date: "2099-01-01" })
    ).rejects.toThrow();
  });
});
