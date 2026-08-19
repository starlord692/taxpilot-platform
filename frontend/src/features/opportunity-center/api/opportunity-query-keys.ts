export const opportunityKeys = {
  all: ["opportunities"] as const,
  collection: (businessId: string) =>
    [...opportunityKeys.all, businessId, "collection"] as const,
};
