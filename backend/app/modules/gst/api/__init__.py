"""GST API exports."""

from app.modules.gst.api.router import router
from app.modules.gst.compliance.api import router as compliance_router
from app.modules.gst.einvoice.api import router as einvoice_router

router.include_router(compliance_router)
router.include_router(einvoice_router)

__all__ = ["router"]
