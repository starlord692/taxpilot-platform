import { apiClient } from "@/lib/api/client";
import type { OpportunityCollectionResponse } from "../types/opportunity.types";

export const opportunityApi = {
  async getCollection(businessId: string): Promise<OpportunityCollectionResponse> {
    const response = await apiClient.get<OpportunityCollectionResponse>(
      "/opportunities",
      { params: { business_id: businessId } },
    );
    return response.data;
  },
};
