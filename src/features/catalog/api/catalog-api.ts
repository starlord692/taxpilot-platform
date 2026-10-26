import { apiClient } from "@/lib/api/client";
import type { CatalogItem, CatalogItemQuery } from "../types/catalog.types";
import { isPreviewMode } from "@/lib/env";

export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

export interface CatalogItemListData {
  items: CatalogItem[];
  total: number;
  limit: number;
  offset: number;
}

export const catalogApi = {
  async list(businessId: string, params?: CatalogItemQuery): Promise<CatalogItem[]> {
    if (isPreviewMode) {
      return [];
    }
    const response = await apiClient.get<ApiResponse<CatalogItemListData>>("/catalog/items", {
      params: { business_id: businessId, ...params },
    });
    return response.data?.data?.items ?? [];
  },

  async get(itemId: string): Promise<CatalogItem> {
    const response = await apiClient.get<ApiResponse<CatalogItem>>(`/catalog/items/${itemId}`);
    return response.data.data;
  },
};
