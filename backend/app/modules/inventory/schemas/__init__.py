"""Inventory schemas package."""

from app.modules.inventory.schemas.product import (
    InventoryResponseBase,
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.modules.inventory.schemas.stock_balance import (
    StockBalanceListResponse,
    StockBalanceResponse,
)
from app.modules.inventory.schemas.stock_movement import (
    StockMovementCreate,
    StockMovementListResponse,
    StockMovementResponse,
)
from app.modules.inventory.schemas.warehouse import (
    WarehouseCreate,
    WarehouseListResponse,
    WarehouseResponse,
    WarehouseUpdate,
)

__all__ = [
    "InventoryResponseBase",
    "ProductCreate",
    "ProductListResponse",
    "ProductResponse",
    "ProductUpdate",
    "StockBalanceListResponse",
    "StockBalanceResponse",
    "StockMovementCreate",
    "StockMovementListResponse",
    "StockMovementResponse",
    "WarehouseCreate",
    "WarehouseListResponse",
    "WarehouseResponse",
    "WarehouseUpdate",
]
