"""Document API exports."""

from fastapi import APIRouter

from app.modules.documents.api.router import router as documents_router
from app.modules.documents.automation.api import router as automation_router
from app.modules.documents.extraction.api import router as extraction_router
from app.modules.documents.review.api import router as review_router

router = APIRouter()
router.include_router(extraction_router)
router.include_router(review_router)
router.include_router(automation_router)
router.include_router(documents_router)

__all__ = ["router"]
