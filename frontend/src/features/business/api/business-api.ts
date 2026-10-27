import { apiClient } from "@/lib/api/client";
import { isPreviewMode } from "@/lib/env";
import type { BusinessSummary, GstRegistration, PaginatedEnvelope } from "../types/business.types";
export const businessApi = {
  async list() { const response = await apiClient.get<PaginatedEnvelope<BusinessSummary>>("/businesses/", { params: { page: 1, page_size: 100, sort: "legal_name" } }); return response.data; },
  async gst(businessId: string) { if (isPreviewMode) return { success: true, message: "Preview mode", data: [], meta: { page: 1, size: 20, total: 0, pages: 0 } } satisfies PaginatedEnvelope<GstRegistration>; const response = await apiClient.get<PaginatedEnvelope<GstRegistration>>("/gst/registrations", { params: { business_id: businessId, page: 1, page_size: 20 } }); return response.data; },
};
