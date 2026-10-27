export interface BusinessSummary { id: string; legal_name: string; trade_name: string | null; business_type: string; status: string; }
export interface GstRegistration { id: string; business_id: string; gstin: string; legal_name: string; trade_name: string | null; registration_type: string; state_code: string; registration_date: string; is_composition_scheme: boolean; is_active: boolean; }
export interface PaginationMeta { page: number; size: number; total: number; pages: number; }
export interface PaginatedEnvelope<T> { success: boolean; message: string; data: T[]; meta: PaginationMeta; }
export type BusinessContextStatus = "initializing" | "no-business" | "selection-required" | "ready" | "unavailable";
