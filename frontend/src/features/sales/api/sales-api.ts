import { apiClient } from "@/lib/api/client";
import type { CanonicalInvoiceDraftInput, CanonicalInvoiceDraftUpdate, Customer, CustomerInput, Invoice, InvoiceSummary, PaginatedEnvelope, SuccessEnvelope } from "../types/sales.types";
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
  async createCustomer(businessId: string, input: CustomerInput) {
    return (await apiClient.post<SuccessEnvelope<Customer>>("/sales/customers", { business_id: businessId, ...input })).data.data;
  },
  async updateCustomer(customerId: string, input: Partial<CustomerInput> & { is_active?: boolean }) {
    return (await apiClient.patch<SuccessEnvelope<Customer>>(`/sales/customers/${customerId}`, input)).data.data;
  },
  async invoices(businessId: string, page: number, pageSize: number) {
    if (isPreviewMode) return { success: true, message: "Preview mode", data: [], meta: { page, size: pageSize, total: 0, pages: 0 } } satisfies PaginatedEnvelope<InvoiceSummary>;
    const response = await apiClient.get<PaginatedEnvelope<InvoiceSummary>>("/sales/workflow/invoices", { params: { business_id: businessId, page, page_size: pageSize } });
    return response.data;
  },
  async invoice(invoiceId: string) {
    const response = await apiClient.get<SuccessEnvelope<Invoice>>(`/sales/workflow/invoices/${invoiceId}`);
    return response.data.data;
  },
  async createInvoice(input: CanonicalInvoiceDraftInput) { return (await apiClient.post<SuccessEnvelope<Invoice>>("/sales/workflow/invoices", input)).data.data; },
  async updateInvoice(id: string, input: CanonicalInvoiceDraftUpdate) { return (await apiClient.patch<SuccessEnvelope<Invoice>>(`/sales/workflow/invoices/${id}`, input)).data.data; },
  async issueInvoice(id: string) { return (await apiClient.post<SuccessEnvelope<Invoice>>(`/sales/workflow/invoices/${id}/issue`)).data.data; },
  async cancelInvoice(id: string) { return (await apiClient.post<SuccessEnvelope<Invoice>>(`/sales/workflow/invoices/${id}/cancel`)).data.data; },
};
