import type { InvoiceStatus } from "../types/sales.types";

export const parsePage = (value: string | null) => { const page = Number(value); return Number.isInteger(page) && page > 0 ? page : 1; };
export const parsePageSize = (value: string | null) => [10, 20, 50].includes(Number(value)) ? Number(value) : 20;
export const formatDate = (value: string | null) => value ? new Intl.DateTimeFormat("en-IN", { dateStyle: "medium" }).format(new Date(value)) : "Unavailable";
export const formatMoney = (value: string | number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(value));
export const titleCase = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
export const statusTone = (status: InvoiceStatus) => status === "paid" ? "success" : status === "cancelled" ? "danger" : status === "issued" ? "info" : "neutral";
