import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "../api/dashboard-api";
import { dashboardKeys } from "../api/dashboard-query-keys";
export function useDashboardActivities(businessId?: string) { const enabled = Boolean(businessId); const expenses = useQuery({ queryKey: dashboardKeys.expenses(businessId ?? "none"), queryFn: () => dashboardApi.expenses(businessId!), enabled, staleTime: 60_000, retry: 1 }); const purchases = useQuery({ queryKey: dashboardKeys.purchases(businessId ?? "none"), queryFn: () => dashboardApi.purchases(businessId!), enabled, staleTime: 60_000, retry: 1 }); return { expenses, purchases }; }
