import { describe, expect, it } from "vitest";
import type { Invoice } from "../types/sales.types";
import { parsePage, parsePageSize, paymentState } from "./sales-format";

const invoice = (overrides: Partial<Invoice> = {}): Invoice => ({ id: "i1", business_id: "b1", customer_id: "c1", invoice_number: "INV-1", invoice_date: "2026-01-01", due_date: "2026-02-01", status: "issued", total_amount: "100", subtotal: "100", discount_amount: "0", taxable_amount: "100", tax_amount: "0", notes: null, lines: [], payments: [], ...overrides });
describe("sales state utilities", () => {
  it("sanitizes pagination without creating API parameters", () => { expect(parsePage("-2")).toBe(1); expect(parsePage("3")).toBe(3); expect(parsePageSize("25")).toBe(20); expect(parsePageSize("50")).toBe(50); });
  it("derives payment state only from invoice detail payments", () => { expect(paymentState(invoice({ payments: [{ id: "p1", invoice_id: "i1", payment_date: "2026-01-02", amount: "40", payment_method: "upi", reference_number: null, notes: null }] }), new Date("2026-01-15")).label).toBe("Partial"); expect(paymentState(invoice(), new Date("2026-03-01")).label).toBe("Overdue"); expect(paymentState(invoice({ status: "paid", payments: [{ id: "p1", invoice_id: "i1", payment_date: "2026-01-02", amount: "100", payment_method: "cash", reference_number: null, notes: null }] })).balance).toBe(0); });
});
