import { apiClient } from "@/lib/api/client";
import { isPreviewMode } from "@/lib/env";
import type { CatalogInput, CatalogItem, CatalogQuery, Page, Success } from "../types/catalog.types";

const empty = (query: CatalogQuery): Page<CatalogItem> => ({ success: true, message: "Preview mode", data: [], meta: { page: query.page, size: query.pageSize, total: 0, pages: 0 } });
export const catalogApi = {
  async items(businessId: string, query: CatalogQuery) { if (isPreviewMode) return empty(query); const params: Record<string, string | number> = { business_id: businessId, page: query.page, page_size: query.pageSize }; if (query.itemType) params.item_type = query.itemType; if (query.status) params.status = query.status; return (await apiClient.get<Page<CatalogItem>>("/catalog/items", { params })).data; },
  async item(businessId: string, id: string) { return (await apiClient.get<Success<CatalogItem>>(`/catalog/items/${id}`, { params: { business_id: businessId } })).data.data; },
  async create(businessId: string, input: CatalogInput) { return (await apiClient.post<Success<CatalogItem>>("/catalog/items", input, { params: { business_id: businessId } })).data.data; },
  async update(businessId: string, id: string, input: Partial<CatalogInput>) { return (await apiClient.patch<Success<CatalogItem>>(`/catalog/items/${id}`, input, { params: { business_id: businessId } })).data.data; },
  async setArchived(businessId: string, id: string, archived: boolean) { return (await apiClient.post<Success<CatalogItem>>(`/catalog/items/${id}/${archived ? "archive" : "restore"}`, undefined, { params: { business_id: businessId } })).data.data; },
};
