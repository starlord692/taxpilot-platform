export type ItemType = "PRODUCT" | "SERVICE";
export type CatalogItemStatus = "ACTIVE" | "ARCHIVED";

export interface InventoryItemProfile {
  stock_tracking: boolean;
  legacy_product_id: string | null;
  default_warehouse_id: string | null;
  reorder_point: string | number | null;
  safety_stock: string | number | null;
}

export interface CatalogItem {
  id: string;
  business_id: string;
  name: string;
  code: string;
  item_type: ItemType;
  status: CatalogItemStatus;
  hsn_sac_code: string | null;
  tax_rate: string | number;
  base_price: string | number;
  unit: string;
  description: string | null;
  inventory_profile: InventoryItemProfile | null;
  created_at: string;
  updated_at: string;
}

export interface CatalogItemQuery {
  status?: CatalogItemStatus;
  item_type?: ItemType;
  q?: string;
  limit?: number;
  offset?: number;
}
