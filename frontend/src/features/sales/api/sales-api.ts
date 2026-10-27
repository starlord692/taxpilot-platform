import { apiClient } from "@/lib/api/client";
import type { Customer, Invoice, InvoiceCreateInput, InvoiceSummary, PaginatedEnvelope, SuccessEnvelope } from "../types/sales.types";
import { isPreviewMode } from "@/lib/env";

export const salesApi = {
  async customers(businessId: string, page: number, pageSize: number) {
    if (isPreviewMode) return { success: true, message: "Preview mode", data: [], meta: { page, size: pageSize, total: 0, pages: 0 } } satisfies PaginatedEnvelope<Customer>;
    const response = await apiClient.get<PaginatedEnvelope<Customer>>("/sales/customers", { params: { business_id: businessId, page, page_size: pageSize } });
    return response.data;
  },
  async customer(customerId: string) {
    const response = await apiClient.get<SuccessEnvelope<Customer>>(`/sales/customers/${customerId}`);
    return response.data.data;
  },
  async invoices(businessId: string, page: number, pageSize: number) {
    if (isPreviewMode) return { success: true, message: "Preview mode", data: [], meta: { page, size: pageSize, total: 0, pages: 0 } } satisfies PaginatedEnvelope<InvoiceSummary>;
    const response = await apiClient.get<PaginatedEnvelope<InvoiceSummary>>("/sales/invoices", { params: { business_id: businessId, page, page_size: pageSize } });
    return response.data;
  },
  async invoice(invoiceId: string) {
    const response = await apiClient.get<SuccessEnvelope<Invoice>>(`/sales/invoices/${invoiceId}`);
    return response.data.data;
  },
  async createInvoice(input: InvoiceCreateInput) {
    if (isPreviewMode) {
      return {
        id: "inv-preview",
        business_id: input.business_id,
        customer_id: input.customer_id,
        invoice_number: input.invoice_number,
        invoice_date: input.invoice_date,
        due_date: input.due_date ?? null,
        status: "draft",
        subtotal: input.subtotal,
        discount_amount: input.discount_amount ?? 0,
        taxable_amount: input.taxable_amount,
        tax_amount: input.tax_amount ?? 0,
        total_amount: input.total_amount,
        notes: input.notes ?? null,
        lines: input.lines.map((line, idx) => ({
          id: `line-${idx}`,
          invoice_id: "inv-preview",
          catalog_item_id: line.catalog_item_id ?? null,
          warehouse_id: line.warehouse_id ?? null,
          description: line.description,
          quantity: line.quantity,
          unit_price: line.unit_price,
          discount: line.discount ?? 0,
          tax_rate: line.tax_rate ?? 0,
          cgst_amount: line.cgst_amount ?? 0,
          sgst_amount: line.sgst_amount ?? 0,
          igst_amount: line.igst_amount ?? 0,
          cess_amount: line.cess_amount ?? 0,
          line_total: line.line_total ?? line.quantity * line.unit_price,
        })),
        payments: [],
      } satisfies Invoice;
    }
    const response = await apiClient.post<SuccessEnvelope<Invoice>>("/sales/invoices", input);
    return response.data.data;
  },
  async issueInvoice(invoiceId: string) {
    if (isPreviewMode) {
      const invoice = await this.invoice(invoiceId);
      return { ...invoice, status: "issued" as const };
    }
    const response = await apiClient.post<SuccessEnvelope<Invoice>>(`/sales/invoices/${invoiceId}/issue`);
    return response.data.data;
  },
  async cancelInvoice(invoiceId: string) {
    if (isPreviewMode) {
      const invoice = await this.invoice(invoiceId);
      return { ...invoice, status: "cancelled" as const };
    }
    const response = await apiClient.post<SuccessEnvelope<Invoice>>(`/sales/invoices/${invoiceId}/cancel`);
    return response.data.data;
  },
};
