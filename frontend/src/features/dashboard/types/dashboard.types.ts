export interface PaginationMeta { page: number; size: number; total: number; pages: number; }
export interface PaginatedEnvelope<T> { success: boolean; message: string; data: T[]; meta: PaginationMeta; }
export interface BusinessSummary { id: string; legal_name: string; trade_name: string | null; business_type: string; status: string; }
export interface GstRegistration { id: string; business_id: string; gstin: string; legal_name: string; trade_name: string | null; registration_type: string; state_code: string; registration_date: string; is_composition_scheme: boolean; is_active: boolean; }
export interface ExpenseActivity { id: string; business_id: string; vendor_id: string | null; expense_number: string; expense_date: string; category: string; status: string; total_amount: string; attachment_count: number; }
export interface PurchaseActivity { id: string; business_id: string; supplier_id: string; purchase_number: string; invoice_number: string; invoice_date: string; due_date: string | null; status: string; total_amount: string; attachment_count: number; }
export interface HealthResponse { success: boolean; message: string; data: { status: string; version: string; environment: string }; }
export type BusinessContextStatus = "loading" | "ready" | "none" | "selection-required" | "error";
