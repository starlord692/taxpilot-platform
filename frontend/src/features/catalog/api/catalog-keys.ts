import type { CatalogQuery } from "../types/catalog.types";
export const catalogKeys = { all: ["catalog"] as const, items: (businessId: string, query: CatalogQuery) => [...catalogKeys.all, "items", businessId, query] as const, item: (businessId: string, id: string) => [...catalogKeys.all, "item", businessId, id] as const };
