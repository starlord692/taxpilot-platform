"use client";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"; import { purchasesApi } from "../api/purchases-api"; import { purchaseKeys } from "../api/purchases-query-keys"; import type { PurchaseInput, PurchaseQuery, SupplierInput, SupplierQuery } from "../types/purchases.types";
export const useSuppliers = (businessId: string, query: SupplierQuery) => useQuery({ queryKey: purchaseKeys.suppliers(businessId, query), queryFn: () => purchasesApi.suppliers(businessId, query), enabled: Boolean(businessId), placeholderData: keepPreviousData });
export const useSupplier = (id: string) => useQuery({ queryKey: purchaseKeys.supplier(id), queryFn: () => purchasesApi.supplier(id), enabled: Boolean(id) });
export const usePurchases = (businessId: string, query: PurchaseQuery) => useQuery({ queryKey: purchaseKeys.invoices(businessId, query), queryFn: () => purchasesApi.invoices(businessId, query), enabled: Boolean(businessId), placeholderData: keepPreviousData });
export const usePurchase = (id: string) => useQuery({ queryKey: purchaseKeys.invoice(id), queryFn: () => purchasesApi.invoice(id), enabled: Boolean(id) });
export function usePurchaseMutations() { const client = useQueryClient(); const refresh = async () => client.invalidateQueries({ queryKey: purchaseKeys.all }); return {
  createSupplier: useMutation({ mutationFn: ({ businessId, input }: { businessId: string; input: SupplierInput }) => purchasesApi.createSupplier(businessId, input), onSuccess: refresh }),
  updateSupplier: useMutation({ mutationFn: ({ id, input }: { id: string; input: Partial<SupplierInput> }) => purchasesApi.updateSupplier(id, input), onSuccess: refresh }),
  deactivateSupplier: useMutation({ mutationFn: purchasesApi.deactivateSupplier, onSuccess: refresh }), reactivateSupplier: useMutation({ mutationFn: purchasesApi.reactivateSupplier, onSuccess: refresh }),
  createPurchase: useMutation({ mutationFn: ({ businessId, input }: { businessId: string; input: PurchaseInput }) => purchasesApi.createInvoice(businessId, input), onSuccess: refresh }),
  updatePurchase: useMutation({ mutationFn: ({ id, input }: { id: string; input: Partial<PurchaseInput> }) => purchasesApi.updateInvoice(id, input), onSuccess: refresh }),
  transition: useMutation({ mutationFn: ({ id, action }: { id: string; action: "approve" | "receive" | "pay" | "cancel" }) => purchasesApi.transition(id, action), onSuccess: refresh }),
}; }
