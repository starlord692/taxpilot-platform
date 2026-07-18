"""Purchase Management API router exports."""

from fastapi import APIRouter

from app.modules.purchases.api.router import router as purchases_router

router = APIRouter()
router.include_router(purchases_router)

__all__ = ["router"]
