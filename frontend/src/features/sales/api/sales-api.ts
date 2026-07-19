import { apiClient } from "@/lib/api/client";
import type { Customer, Invoice, InvoiceSummary, PaginatedEnvelope, SuccessEnvelope } from "../types/sales.types";
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
};
