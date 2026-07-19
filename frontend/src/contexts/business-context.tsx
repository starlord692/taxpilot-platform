"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/contexts/auth-context";
import { businessApi } from "@/features/business/api/business-api";
import { businessKeys } from "@/features/business/api/business-query-keys";
import type { BusinessContextStatus, BusinessSummary } from "@/features/business/types/business.types";
import { clearBusinessPreference, readBusinessPreference, writeBusinessPreference } from "@/features/business/utils/business-preference";
import { resolveBusinessSelection } from "@/features/business/utils/business-selection";
import { isPreviewMode } from "@/lib/env";

const previewBusiness: BusinessSummary = { id: "preview-business", legal_name: "TaxPilot Preview Business", trade_name: "Preview Workspace", business_type: "company", status: "active" };

interface BusinessContextValue { businesses: BusinessSummary[]; activeBusiness: BusinessSummary | null; activeBusinessId: string | null; status: BusinessContextStatus; selectBusiness: (id: string) => Promise<boolean>; revalidateBusiness: () => Promise<unknown>; }
const BusinessContext = createContext<BusinessContextValue | null>(null);
export function BusinessProvider({ children }: { children: React.ReactNode }) { const { status: authStatus } = useAuth(); const queryClient = useQueryClient(); const [activeId, setActiveId] = useState<string | null>(null); const query = useQuery({ queryKey: businessKeys.list(), queryFn: businessApi.list, enabled: authStatus === "authenticated" && !isPreviewMode, staleTime: 300_000, retry: 1 }); const businesses = useMemo(() => isPreviewMode ? [previewBusiness] : (query.data?.data ?? []), [query.data?.data]);
  useEffect(() => { if (isPreviewMode) { setActiveId(previewBusiness.id); return; } if (authStatus !== "authenticated") { setActiveId(null); return; } if (!query.isSuccess) return; const resolution = resolveBusinessSelection(businesses, readBusinessPreference()); if (resolution.business) { setActiveId(resolution.business.id); writeBusinessPreference(resolution.business.id); } else { setActiveId(null); if (readBusinessPreference()) clearBusinessPreference(); } }, [authStatus, query.isSuccess, businesses]);
  const activeBusiness = isPreviewMode ? previewBusiness : (businesses.find((business) => business.id === activeId) ?? null); let status: BusinessContextStatus = isPreviewMode ? "ready" : "initializing"; if (!isPreviewMode && query.isError) status = "unavailable"; else if (!isPreviewMode && query.isSuccess && !businesses.length) status = "no-business"; else if (!isPreviewMode && query.isSuccess && activeBusiness) status = "ready"; else if (!isPreviewMode && query.isSuccess && businesses.length > 1) status = "selection-required";
  const selectBusiness = useCallback(async (id: string) => { if (!businesses.some((business) => business.id === id)) return false; await queryClient.cancelQueries({ queryKey: ["dashboard"] }); setActiveId(id); writeBusinessPreference(id); await queryClient.invalidateQueries({ queryKey: ["dashboard"] }); return true; }, [businesses, queryClient]);
  const value = useMemo(() => ({ businesses, activeBusiness, activeBusinessId: activeBusiness?.id ?? null, status, selectBusiness, revalidateBusiness: isPreviewMode ? async () => undefined : query.refetch }), [businesses, activeBusiness, status, selectBusiness, query.refetch]); return <BusinessContext.Provider value={value}>{children}</BusinessContext.Provider>; }
export function useBusiness() { const context = useContext(BusinessContext); if (!context) throw new Error("useBusiness must be used within BusinessProvider"); return context; }
