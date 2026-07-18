"""Sales document automation strategy."""

import uuid
from typing import Any

from app.modules.documents.automation.exceptions import AutomationValidationException
from app.modules.documents.automation.mappers import SalesMapper
from app.modules.documents.automation.models import AutomationType
from app.modules.documents.extraction.models import ExtractedDocument
from app.modules.documents.models import DocumentType
from app.modules.documents.review.schemas import DocumentValidationResponse
from app.modules.sales.schemas import InvoiceCreateRequest, InvoiceResponse
from app.modules.sales.services import SalesInvoiceService


class SalesAutomationStrategy:
    """Automate approved sales invoice documents."""

    automation_type = AutomationType.SALES
    erp_record_type = "sales_invoice"

    def __init__(
        self,
        *,
        sales_service: SalesInvoiceService,
        mapper: SalesMapper | None = None,
    ) -> None:
        """Initialize dependencies."""
        self._sales_service = sales_service
        self._mapper = mapper or SalesMapper()

    def supports(self, extracted_document: ExtractedDocument) -> bool:
        """Return whether this is a sales invoice."""
        return extracted_document.document_type == DocumentType.SALES_INVOICE

    def validate(
        self,
        extracted_document: ExtractedDocument,
        validation: DocumentValidationResponse,
    ) -> None:
        """Validate sales automation readiness."""
        _ = extracted_document
        if not validation.ready_for_automation:
            raise AutomationValidationException("Document is not ready for automation")

    def map(self, extracted_document: ExtractedDocument) -> InvoiceCreateRequest:
        """Map extracted fields to a sales request."""
        return self._mapper.map(extracted_document)

    async def execute(
        self,
        request: object,
        *,
        business_id: uuid.UUID,
    ) -> InvoiceResponse:
        """Create invoice through the Sales service."""
        _ = business_id
        return await self._sales_service.create_invoice(
            InvoiceCreateRequest.model_validate(request)
        )

    def result_id(self, result: Any) -> uuid.UUID:
        """Return created sales invoice UUID."""
        return InvoiceResponse.model_validate(result).id
