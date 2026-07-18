"""Inventory API router exports."""

from fastapi import APIRouter

from app.modules.inventory.api.inventory_router import router as inventory_router
from app.modules.inventory.api.product_router import router as product_router
from app.modules.inventory.api.warehouse_router import router as warehouse_router

router = APIRouter()
router.include_router(product_router)
router.include_router(warehouse_router)
router.include_router(inventory_router)

__all__ = ["router"]
