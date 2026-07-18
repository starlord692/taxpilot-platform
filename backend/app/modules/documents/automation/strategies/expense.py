"""Expense document automation strategy."""

import uuid
from typing import Any

from app.modules.documents.automation.exceptions import AutomationValidationException
from app.modules.documents.automation.mappers import ExpenseMapper
from app.modules.documents.automation.models import AutomationType
from app.modules.documents.extraction.models import ExtractedDocument
from app.modules.documents.models import DocumentType
from app.modules.documents.review.schemas import DocumentValidationResponse
from app.modules.expenses.schemas import ExpenseCreate, ExpenseResponse
from app.modules.expenses.services import ExpenseService


class ExpenseAutomationStrategy:
    """Automate approved expense receipt documents."""

    automation_type = AutomationType.EXPENSE
    erp_record_type = "expense"

    def __init__(
        self,
        *,
        expense_service: ExpenseService,
        mapper: ExpenseMapper | None = None,
    ) -> None:
        """Initialize dependencies."""
        self._expense_service = expense_service
        self._mapper = mapper or ExpenseMapper()

    def supports(self, extracted_document: ExtractedDocument) -> bool:
        """Return whether this is an expense receipt."""
        return extracted_document.document_type == DocumentType.EXPENSE_RECEIPT

    def validate(
        self,
        extracted_document: ExtractedDocument,
        validation: DocumentValidationResponse,
    ) -> None:
        """Validate expense automation readiness."""
        _ = extracted_document
        if not validation.ready_for_automation:
            raise AutomationValidationException("Document is not ready for automation")

    def map(self, extracted_document: ExtractedDocument) -> ExpenseCreate:
        """Map extracted fields to an expense request."""
        return self._mapper.map(extracted_document)

    async def execute(
        self,
        request: object,
        *,
        business_id: uuid.UUID,
    ) -> ExpenseResponse:
        """Create expense through the Expense service."""
        return await self._expense_service.create_expense(
            ExpenseCreate.model_validate(request),
            business_id=business_id,
        )

    def result_id(self, result: Any) -> uuid.UUID:
        """Return created expense UUID."""
        return ExpenseResponse.model_validate(result).id
