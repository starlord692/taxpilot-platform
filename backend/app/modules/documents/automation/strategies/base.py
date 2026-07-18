"""Automation strategy interface."""

import uuid
from typing import Any, Protocol

from app.modules.documents.automation.models import AutomationType
from app.modules.documents.extraction.models import ExtractedDocument
from app.modules.documents.review.schemas import DocumentValidationResponse


class AutomationStrategy(Protocol):
    """Strategy contract for ERP automation targets."""

    automation_type: AutomationType
    erp_record_type: str

    def supports(self, extracted_document: ExtractedDocument) -> bool:
        """Return whether the strategy supports the document."""
        ...

    def validate(
        self,
        extracted_document: ExtractedDocument,
        validation: DocumentValidationResponse,
    ) -> None:
        """Perform final automation validation."""
        ...

    def map(self, extracted_document: ExtractedDocument) -> object:
        """Map extracted fields into an existing ERP request schema."""
        ...

    async def execute(self, request: object, *, business_id: uuid.UUID) -> Any:
        """Execute automation through an existing ERP service."""
        ...

    def result_id(self, result: Any) -> uuid.UUID:
        """Return created ERP record UUID from service response."""
        ...
