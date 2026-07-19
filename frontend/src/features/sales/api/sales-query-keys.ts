export const salesKeys = {
  all: ["sales"] as const,
  customers: (businessId: string, page: number, pageSize: number) => [...salesKeys.all, "customers", businessId, page, pageSize] as const,
  customer: (id: string) => [...salesKeys.all, "customer", id] as const,
  invoices: (businessId: string, page: number, pageSize: number) => [...salesKeys.all, "invoices", businessId, page, pageSize] as const,
  invoice: (id: string) => [...salesKeys.all, "invoice", id] as const,
};
