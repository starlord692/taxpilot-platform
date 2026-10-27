"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { catalogApi } from "../api/catalog-api";
import type { CatalogItemQuery } from "../types/catalog.types";

export const catalogKeys = {
  all: ["catalog"] as const,
  items: (businessId: string, query?: CatalogItemQuery) =>
    [...catalogKeys.all, "items", businessId, query] as const,
  item: (id: string) => [...catalogKeys.all, "item", id] as const,
};

export function useCatalogItems(businessId: string, query?: CatalogItemQuery) {
  return useQuery({
    queryKey: catalogKeys.items(businessId, query),
    queryFn: () => catalogApi.list(businessId, query),
    enabled: Boolean(businessId),
    placeholderData: keepPreviousData,
  });
}

export function useCatalogItem(id: string) {
  return useQuery({
    queryKey: catalogKeys.item(id),
    queryFn: () => catalogApi.get(id),
    enabled: Boolean(id),
  });
}
