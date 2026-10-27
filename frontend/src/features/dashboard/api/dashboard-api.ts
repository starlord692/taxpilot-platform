import { apiClient } from "@/lib/api/client";
import { isPreviewMode } from "@/lib/env";
import type { ExpenseActivity, GstRegistration, HealthResponse, PaginatedEnvelope, PurchaseActivity } from "../types/dashboard.types";

const emptyPreview = <T,>(size: number): PaginatedEnvelope<T> => ({ success: true, message: "Preview mode", data: [], meta: { page: 1, size, total: 0, pages: 0 } });
export const dashboardApi = {
  async gstRegistrations(businessId: string) { if (isPreviewMode) return emptyPreview<GstRegistration>(20); const response = await apiClient.get<PaginatedEnvelope<GstRegistration>>("/gst/registrations", { params: { business_id: businessId, page: 1, page_size: 20 } }); return response.data; },
  async expenses(businessId: string) { if (isPreviewMode) return emptyPreview<ExpenseActivity>(5); const response = await apiClient.get<PaginatedEnvelope<ExpenseActivity>>("/expenses", { params: { business_id: businessId, page: 1, page_size: 5, sort: "-expense_date" } }); return response.data; },
  async purchases(businessId: string) { if (isPreviewMode) return emptyPreview<PurchaseActivity>(5); const response = await apiClient.get<PaginatedEnvelope<PurchaseActivity>>("/purchases", { params: { business_id: businessId, page: 1, page_size: 5, sort: "-invoice_date" } }); return response.data; },
  async health() { if (isPreviewMode) return { success: true, message: "Preview mode", data: { status: "preview", version: "frontend", environment: "development" } } satisfies HealthResponse; const response = await apiClient.get<HealthResponse>("/health"); return response.data; },
};
