"use client";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { catalogApi } from "../api/catalog-api";
import { catalogKeys } from "../api/catalog-keys";
import type { CatalogInput, CatalogQuery } from "../types/catalog.types";
export const useCatalogItems = (businessId: string, query: CatalogQuery) => useQuery({ queryKey: catalogKeys.items(businessId, query), queryFn: () => catalogApi.items(businessId, query), enabled: Boolean(businessId), placeholderData: keepPreviousData });
export const useCatalogItem = (businessId: string, id: string) => useQuery({ queryKey: catalogKeys.item(businessId, id), queryFn: () => catalogApi.item(businessId, id), enabled: Boolean(businessId && id) });
export function useCatalogMutations() { const client = useQueryClient(); const refresh = () => client.invalidateQueries({ queryKey: catalogKeys.all }); return { create: useMutation({ mutationFn: ({ businessId, input }: { businessId: string; input: CatalogInput }) => catalogApi.create(businessId, input), onSuccess: refresh }), update: useMutation({ mutationFn: ({ businessId, id, input }: { businessId: string; id: string; input: Partial<CatalogInput> }) => catalogApi.update(businessId, id, input), onSuccess: refresh }), setArchived: useMutation({ mutationFn: ({ businessId, id, archived }: { businessId: string; id: string; archived: boolean }) => catalogApi.setArchived(businessId, id, archived), onSuccess: refresh }) }; }
