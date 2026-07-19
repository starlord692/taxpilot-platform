import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "../api/dashboard-api";
import { dashboardKeys } from "../api/dashboard-query-keys";
import { useBusiness } from "@/contexts/business-context";
import { useDashboardActivities } from "./use-dashboard-activities";
import { useDashboardHealth } from "./use-dashboard-health";
export function useDashboardViewModel() { const shared = useBusiness(); const businessId = shared.activeBusiness?.id; const gst = useQuery({ queryKey: dashboardKeys.gst(businessId ?? "none"), queryFn: () => dashboardApi.gstRegistrations(businessId!), enabled: Boolean(businessId), staleTime: 300_000, retry: 1 }); const activity = useDashboardActivities(businessId); const health = useDashboardHealth(); const timestamps = [gst.dataUpdatedAt, activity.expenses.dataUpdatedAt, activity.purchases.dataUpdatedAt, health.dataUpdatedAt].filter(Boolean); const contextStatus = shared.status === "initializing" ? "loading" : shared.status === "no-business" ? "none" : shared.status === "selection-required" ? "selection-required" : shared.status === "unavailable" ? "error" : "ready"; const context = { contextStatus, refetch: shared.revalidateBusiness }; return { context, business: shared.activeBusiness, gst, activity, health, lastSync: timestamps.length ? Math.max(...timestamps) : null }; }
