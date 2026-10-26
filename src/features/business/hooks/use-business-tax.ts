import { useQuery } from "@tanstack/react-query";
import { businessApi } from "../api/business-api";
import { businessKeys } from "../api/business-query-keys";
export function useBusinessTax(businessId?: string) { return useQuery({ queryKey: businessKeys.gst(businessId ?? "none"), queryFn: () => businessApi.gst(businessId!), enabled: Boolean(businessId), staleTime: 300_000, retry: 1 }); }
