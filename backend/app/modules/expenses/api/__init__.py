"""Expense API router exports."""

from fastapi import APIRouter

from app.modules.expenses.api.expense_router import router as expense_router
from app.modules.expenses.api.vendor_router import router as vendor_router

router = APIRouter()
router.include_router(vendor_router)
router.include_router(expense_router)

__all__ = ["router"]
