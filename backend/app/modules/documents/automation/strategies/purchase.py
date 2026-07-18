"""Purchase document automation strategy."""

import uuid
from typing import Any

from app.modules.documents.automation.exceptions import AutomationValidationException
from app.modules.documents.automation.mappers import PurchaseMapper
from app.modules.documents.automation.models import AutomationType
from app.modules.documents.extraction.models import ExtractedDocument
from app.modules.documents.models import DocumentType
from app.modules.documents.review.schemas import DocumentValidationResponse
from app.modules.purchases.schemas import (
    PurchaseInvoiceCreate,
    PurchaseInvoiceResponse,
)
from app.modules.purchases.services import PurchaseService


class PurchaseAutomationStrategy:
    """Automate approved purchase invoice documents."""

    automation_type = AutomationType.PURCHASE
    erp_record_type = "purchase_invoice"

    def __init__(
        self,
        *,
        purchase_service: PurchaseService,
        mapper: PurchaseMapper | None = None,
    ) -> None:
        """Initialize dependencies."""
        self._purchase_service = purchase_service
        self._mapper = mapper or PurchaseMapper()

    def supports(self, extracted_document: ExtractedDocument) -> bool:
        """Return whether this is a purchase invoice."""
        return extracted_document.document_type == DocumentType.PURCHASE_INVOICE

    def validate(
        self,
        extracted_document: ExtractedDocument,
        validation: DocumentValidationResponse,
    ) -> None:
        """Validate purchase automation readiness."""
        _ = extracted_document
        if not validation.ready_for_automation:
            raise AutomationValidationException("Document is not ready for automation")

    def map(self, extracted_document: ExtractedDocument) -> PurchaseInvoiceCreate:
        """Map extracted fields to a purchase request."""
        return self._mapper.map(extracted_document)

    async def execute(
        self,
        request: object,
        *,
        business_id: uuid.UUID,
    ) -> PurchaseInvoiceResponse:
        """Create purchase through the Purchase service."""
        purchase_request = PurchaseInvoiceCreate.model_validate(request)
        return await self._purchase_service.create_purchase(
            purchase_request,
            business_id=business_id,
        )

    def result_id(self, result: Any) -> uuid.UUID:
        """Return created purchase invoice UUID."""
        return PurchaseInvoiceResponse.model_validate(result).id
