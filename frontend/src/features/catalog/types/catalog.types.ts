export type ItemType = "product" | "service";
export type CatalogStatus = "active" | "archived";
export type CatalogItem = { id: string; business_id: string; code: string | null; name: string; description: string | null; item_type: ItemType; status: CatalogStatus; category: string | null; purchase_price: string | number; selling_price: string | number; default_unit: string; barcode: string | null; hsn_code: string | null; sac_code: string | null; gst_rate: string | number; cess_rate: string | number };
export type CatalogInput = Omit<CatalogItem, "id" | "business_id" | "status">;
export type CatalogQuery = { page: number; pageSize: number; itemType?: ItemType; status?: CatalogStatus };
export type Page<T> = { success: boolean; message: string; data: T[]; meta: { page: number; size: number; total: number; pages: number } };
export type Success<T> = { success: boolean; message: string; data: T };
