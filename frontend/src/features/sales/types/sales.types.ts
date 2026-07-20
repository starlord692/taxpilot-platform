export type PaginatedEnvelope<T> = { success: boolean; message: string; data: T[]; meta: { page: number; size: number; total: number; pages: number } };
export type SuccessEnvelope<T> = { success: boolean; message: string; data: T };

export type Customer = {
  id: string; business_id: string; customer_code: string; name: string;
  email: string | null; phone: string | null; gstin: string | null; pan: string | null;
  billing_address: string | null; shipping_address: string | null; is_active: boolean;
};
export type CustomerInput = {
  customer_code: string; name: string; email: string | null; phone: string | null;
  gstin: string | null; pan: string | null; billing_address: string | null; shipping_address: string | null;
};

export type InvoiceStatus = "draft" | "issued" | "partially_paid" | "paid" | "cancelled";
export type InvoiceSummary = {
  id: string; business_id: string; customer_id: string; invoice_number: string;
  invoice_date: string; due_date: string | null; status: InvoiceStatus; total_amount: string | number;
};
export type InvoiceLine = {
  id: string; invoice_id: string; description: string; quantity: string | number;
  unit_price: string | number; discount: string | number; tax_rate: string | number;
  cgst_amount: string | number; sgst_amount: string | number; igst_amount: string | number;
  cess_amount: string | number; line_total: string | number;
};
export type InvoicePayment = {
  id: string; invoice_id: string; payment_date: string; amount: string | number;
  payment_method: "cash" | "bank_transfer" | "upi" | "card" | "cheque" | "other";
  reference_number: string | null; notes: string | null;
};
export type Invoice = InvoiceSummary & {
  subtotal: string | number; discount_amount: string | number; taxable_amount: string | number;
  tax_amount: string | number; notes: string | null; lines: InvoiceLine[]; payments: InvoicePayment[];
};
