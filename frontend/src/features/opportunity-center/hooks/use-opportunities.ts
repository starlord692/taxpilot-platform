import { useQuery } from "@tanstack/react-query";
import { opportunityApi } from "../api/opportunity-api";
import { opportunityKeys } from "../api/opportunity-query-keys";

export function useOpportunities(businessId: string | null) {
  return useQuery({
    queryKey: opportunityKeys.collection(businessId ?? "none"),
    queryFn: () => opportunityApi.getCollection(businessId!),
    enabled: Boolean(businessId),
    retry: 1,
  });
}
