import type { DocumentStatus, DocumentType } from "../types/documents.types";

export const documentTypes = ["unknown", "sales_invoice", "purchase_invoice", "expense_receipt", "bank_statement", "gst_certificate", "pan", "other"] as const;
export const documentStatuses = ["uploaded", "ocr_pending", "ocr_running", "ocr_completed", "ocr_failed"] as const;
export const allowedDocumentMimeTypes = ["application/pdf", "image/png", "image/jpeg", "image/webp", "image/tiff"] as const;
export const page = (value: string | null) => Math.max(1, Number(value) || 1);
export const size = (value: string | null) => [10, 20, 50, 100].includes(Number(value)) ? Number(value) : 20;
export const type = (value: string | null): DocumentType | undefined => documentTypes.includes(value as DocumentType) ? value as DocumentType : undefined;
export const status = (value: string | null): DocumentStatus | undefined => documentStatuses.includes(value as DocumentStatus) ? value as DocumentStatus : undefined;
export const bytes = (value: number) => value < 1024 ? `${value} B` : value < 1048576 ? `${(value / 1024).toFixed(1)} KB` : `${(value / 1048576).toFixed(1)} MB`;
export const confidence = (value: string | number) => { const numeric = Number(value); return Math.max(0, Math.min(100, Math.round(numeric <= 1 ? numeric * 100 : numeric))); };
export const title = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());

export function businessDocumentStatus(statusValue: DocumentStatus) {
  if (statusValue === "ocr_pending" || statusValue === "uploaded") return "Ready to read";
  if (statusValue === "ocr_running") return "Reading document";
  if (statusValue === "ocr_completed") return "Information read";
  return "Reading failed";
}
