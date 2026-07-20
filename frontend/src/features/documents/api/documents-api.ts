import { apiClient } from "@/lib/api/client";
import { ApiClientError } from "@/lib/api/errors";
import { isPreviewMode } from "@/lib/env";
import type { AutomationResult, AutomationRun, Document, DocumentList, DocumentQuery, DocumentType, Extraction, Page, PendingReview, ReviewInput, Success, Validation } from "../types/documents.types";

const empty = <T,>(page: number, size: number): Page<T> => ({ success: true, message: "Preview mode", data: [], meta: { page, size, total: 0, pages: 0 } });
const optional = async <T,>(request: () => Promise<T>): Promise<T | null> => { try { return await request(); } catch (error) { if (error instanceof ApiClientError && error.status === 404) return null; throw error; } };

export const documentsApi = {
  async list(businessId: string, query: DocumentQuery) { if (isPreviewMode) return empty<DocumentList>(query.page, query.pageSize); const params: Record<string, string | number> = { business_id: businessId, page: query.page, page_size: query.pageSize }; if (query.documentType) params.document_type = query.documentType; if (query.status) params.status_filter = query.status; return (await apiClient.get<Page<DocumentList>>("/documents", { params })).data; },
  async detail(businessId: string, id: string) { return (await apiClient.get<Success<Document>>(`/documents/${id}`, { params: { business_id: businessId } })).data.data; },
  async upload(businessId: string, file: File, documentType: DocumentType, onProgress?: (value: number) => void) { return (await apiClient.post<Success<Document>>("/documents/upload", file, { params: { business_id: businessId, filename: file.name, document_type: documentType }, headers: { "Content-Type": file.type || "application/octet-stream" }, onUploadProgress: event => onProgress?.(event.total ? Math.round(event.loaded / event.total * 100) : 0) })).data.data; },
  async ocr(businessId: string, id: string) { return (await apiClient.post<Success<Document>>(`/documents/${id}/ocr`, { provider: "default", language: null }, { params: { business_id: businessId } })).data.data; },
  async extract(businessId: string, id: string, useAi = true) { return (await apiClient.post<Success<Extraction>>(`/documents/${id}/extract`, { use_ai: useAi }, { params: { business_id: businessId } })).data.data; },
  async extraction(businessId: string, id: string) { return optional(async () => (await apiClient.get<Success<Extraction>>(`/documents/${id}/extraction`, { params: { business_id: businessId } })).data.data); },
  async validate(businessId: string, id: string) { return (await apiClient.post<Success<Validation>>(`/documents/${id}/validate`, undefined, { params: { business_id: businessId } })).data.data; },
  async validation(businessId: string, id: string) { return optional(async () => (await apiClient.get<Success<Validation>>(`/documents/${id}/validation`, { params: { business_id: businessId } })).data.data); },
  async review(businessId: string, id: string, input: ReviewInput) { return (await apiClient.post<Success<Validation>>(`/documents/${id}/review`, input, { params: { business_id: businessId } })).data.data; },
  async automate(businessId: string, id: string, key: string) { return (await apiClient.post<Success<AutomationResult>>(`/documents/${id}/automate`, { idempotency_key: key }, { params: { business_id: businessId } })).data.data; },
  async pending(businessId: string, page: number, size: number) { if (isPreviewMode) return empty<PendingReview>(page, size); return (await apiClient.get<Page<PendingReview>>("/documents/review/pending", { params: { business_id: businessId, page, page_size: size } })).data; },
  async automation(businessId: string, id: string) { return optional(async () => (await apiClient.get<Success<AutomationRun>>(`/documents/${id}/automation`, { params: { business_id: businessId } })).data.data); },
};
