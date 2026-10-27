import { describe, expect, it } from "vitest";
import { invoiceCreateSchema, invoiceLineSchema } from "./sales-schemas";

describe("sales-schemas", () => {
  const validLine = {
    description: "Web development services",
    quantity: 2,
    unit_price: 1500,
    discount: 100,
    tax_rate: 18,
    cgst_amount: 261,
    sgst_amount: 261,
    igst_amount: 0,
    cess_amount: 0,
    line_total: 3422,
  };

  const validInvoice = {
    customer_id: "c87a5525-45d2-430c-9a41-faea72688461",
    invoice_number: "INV-2026-0001",
    invoice_date: "2026-04-01",
    due_date: "2026-04-30",
    notes: "Payment due within 30 days.",
    lines: [validLine],
  };

  it("validates a complete, valid sales invoice payload", () => {
    const result = invoiceCreateSchema.safeParse(validInvoice);
    expect(result.success).toBe(true);
  });

  it("allows due_date and notes to be null or omitted", () => {
    const withoutOptional = {
      customer_id: "c87a5525-45d2-430c-9a41-faea72688461",
      invoice_number: "INV-2026-0002",
      invoice_date: "2026-04-01",
      lines: [validLine],
    };
    const result = invoiceCreateSchema.safeParse(withoutOptional);
    expect(result.success).toBe(true);
  });

  it("rejects an empty customer_id", () => {
    const result = invoiceCreateSchema.safeParse({
      ...validInvoice,
      customer_id: "",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.flatten().fieldErrors.customer_id).toBeDefined();
    }
  });

  it("rejects an empty invoice_number", () => {
    const result = invoiceCreateSchema.safeParse({
      ...validInvoice,
      invoice_number: "   ",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.flatten().fieldErrors.invoice_number).toBeDefined();
    }
  });

  it("rejects an invoice_number longer than 50 characters", () => {
    const result = invoiceCreateSchema.safeParse({
      ...validInvoice,
      invoice_number: "A".repeat(51),
    });
    expect(result.success).toBe(false);
  });

  it("rejects an invoice with due_date earlier than invoice_date", () => {
    const result = invoiceCreateSchema.safeParse({
      ...validInvoice,
      invoice_date: "2026-04-15",
      due_date: "2026-04-10",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.flatten().fieldErrors.due_date?.[0]).toContain(
        "Due date cannot be before invoice date"
      );
    }
  });

  it("rejects an invoice with empty lines array", () => {
    const result = invoiceCreateSchema.safeParse({
      ...validInvoice,
      lines: [],
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.flatten().fieldErrors.lines).toBeDefined();
    }
  });

  it("rejects a line with an empty description", () => {
    const result = invoiceLineSchema.safeParse({
      ...validLine,
      description: "  ",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.flatten().fieldErrors.description).toBeDefined();
    }
  });

  it("rejects a line with zero or negative quantity", () => {
    expect(
      invoiceLineSchema.safeParse({ ...validLine, quantity: 0 }).success
    ).toBe(false);
    expect(
      invoiceLineSchema.safeParse({ ...validLine, quantity: -1 }).success
    ).toBe(false);
  });

  it("rejects a line with zero or negative unit price", () => {
    expect(
      invoiceLineSchema.safeParse({ ...validLine, unit_price: 0 }).success
    ).toBe(false);
    expect(
      invoiceLineSchema.safeParse({ ...validLine, unit_price: -50 }).success
    ).toBe(false);
  });

  it("rejects a line with negative discount or tax rate", () => {
    expect(
      invoiceLineSchema.safeParse({ ...validLine, discount: -10 }).success
    ).toBe(false);
    expect(
      invoiceLineSchema.safeParse({ ...validLine, tax_rate: -5 }).success
    ).toBe(false);
  });

  it("rejects an invoice where a line discount exceeds the gross line amount", () => {
    const result = invoiceCreateSchema.safeParse({
      ...validInvoice,
      lines: [
        {
          ...validLine,
          quantity: 1,
          unit_price: 100,
          discount: 150, // exceeds gross 100
        },
      ],
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.flatten().fieldErrors.lines?.[0]).toContain(
        "Line discount cannot exceed gross line amount"
      );
    }
  });
});
