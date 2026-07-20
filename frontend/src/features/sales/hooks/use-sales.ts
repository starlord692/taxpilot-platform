"use client";
import { keepPreviousData, useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { salesApi } from "../api/sales-api";
import { salesKeys } from "../api/sales-query-keys";
import type { CustomerInput } from "../types/sales.types";

export const useCustomers = (businessId: string, page: number, pageSize: number) => useQuery({ queryKey: salesKeys.customers(businessId, page, pageSize), queryFn: () => salesApi.customers(businessId, page, pageSize), enabled: Boolean(businessId), placeholderData: keepPreviousData });
export const useCustomer = (id: string) => useQuery({ queryKey: salesKeys.customer(id), queryFn: () => salesApi.customer(id), enabled: Boolean(id) });
export const useInvoices = (businessId: string, page: number, pageSize: number) => useQuery({ queryKey: salesKeys.invoices(businessId, page, pageSize), queryFn: () => salesApi.invoices(businessId, page, pageSize), enabled: Boolean(businessId), placeholderData: keepPreviousData });
export const useInvoice = (id: string) => useQuery({ queryKey: salesKeys.invoice(id), queryFn: () => salesApi.invoice(id), enabled: Boolean(id) });
export function useCustomerNames(ids: string[]) {
  const unique = [...new Set(ids)];
  const results = useQueries({ queries: unique.map((id) => ({ queryKey: salesKeys.customer(id), queryFn: () => salesApi.customer(id), staleTime: 60_000 })) });
  return new Map(results.flatMap((result, index) => result.data ? [[unique[index], result.data.name] as const] : []));
}
export function useCustomerMutations() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: salesKeys.all });
  return {
    create: useMutation({ mutationFn: ({ businessId, input }: { businessId: string; input: CustomerInput }) => salesApi.createCustomer(businessId, input), onSuccess: refresh }),
    update: useMutation({ mutationFn: ({ id, input }: { id: string; input: Partial<CustomerInput> & { is_active?: boolean } }) => salesApi.updateCustomer(id, input), onSuccess: refresh }),
  };
}
