import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "../api/dashboard-api";
import { dashboardKeys } from "../api/dashboard-query-keys";
export function useDashboardHealth() { return useQuery({ queryKey: dashboardKeys.health(), queryFn: dashboardApi.health, staleTime: 30_000, retry: 1, refetchOnReconnect: true }); }
