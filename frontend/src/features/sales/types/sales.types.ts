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
  id: string; catalog_item_id: string; description: string; quantity: string | number;
  unit_price: string | number; discount: string | number; tax_rate: string | number; line_total: string | number;
};
export type Invoice = InvoiceSummary & {
  subtotal: string | number; discount_amount: string | number; taxable_amount: string | number;
  tax_amount: string | number; round_off: string | number; notes: string | null; lines: InvoiceLine[];
};
export type CanonicalInvoiceLineInput = { catalog_item_id: string; quantity: number; unit_price: number; discount: number };
export type CanonicalInvoiceDraftInput = { business_id: string; customer_id: string; invoice_date: string; due_date: string | null; notes: string | null; round_off: number; lines: CanonicalInvoiceLineInput[] };
export type CanonicalInvoiceDraftUpdate = Omit<CanonicalInvoiceDraftInput, "business_id" | "customer_id">;
