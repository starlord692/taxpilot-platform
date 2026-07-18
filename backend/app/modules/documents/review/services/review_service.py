"""Document validation and human review service."""

import uuid
from collections.abc import Callable
from decimal import Decimal
from typing import Any, Protocol

from app.common.events import EventDispatcher
from app.common.models.abstract.timestamp import utc_now
from app.common.pagination import Page, PaginationParams
from app.modules.documents.extraction.models import (
    ExtractedDocument,
    ExtractedField,
    ExtractedFieldSource,
)
from app.modules.documents.review.events import (
    CorrectionRequestedEvent,
    DocumentReadyForAutomationEvent,
    ReviewApprovedEvent,
    ReviewRejectedEvent,
    ValidationCompletedEvent,
)
from app.modules.documents.review.exceptions import (
    DocumentReviewNotFoundException,
    DocumentReviewValidationException,
)
from app.modules.documents.review.models import (
    DocumentReview,
    ReviewDecision,
    ReviewDecisionType,
    ReviewRevision,
    ReviewStatus,
    ValidationIssue,
    ValidationSeverity,
)
from app.modules.documents.review.schemas import (
    DocumentReviewRequest,
    DocumentReviewResponse,
    DocumentValidationResponse,
)
from app.modules.documents.review.validators import BusinessValidationPipeline


class ExtractedDocumentRepositoryProtocol(Protocol):
    """Repository behavior required for extracted documents."""

    async def get_by_document_id(
        self,
        document_id: uuid.UUID,
    ) -> ExtractedDocument | None:
        """Return extracted document by source document UUID."""
        ...


class ExtractedFieldRepositoryProtocol(Protocol):
    """Repository behavior required for extracted fields."""

    async def create(self, extracted_field: ExtractedField) -> ExtractedField:
        """Persist extracted field."""
        ...


class ValidationIssueRepositoryProtocol(Protocol):
    """Repository behavior required for validation issues."""

    async def create(self, issue: ValidationIssue) -> ValidationIssue:
        """Persist validation issue."""
        ...

    async def list_by_document(self, document_id: uuid.UUID) -> list[ValidationIssue]:
        """Return validation issues."""
        ...


class DocumentReviewRepositoryProtocol(Protocol):
    """Repository behavior required for document reviews."""

    async def create(self, review: DocumentReview) -> DocumentReview:
        """Persist document review."""
        ...

    async def get_by_document_id(self, document_id: uuid.UUID) -> DocumentReview | None:
        """Return review by document UUID."""
        ...

    async def list_pending(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[DocumentReview]:
        """Return pending reviews."""
        ...


class ReviewRevisionRepositoryProtocol(Protocol):
    """Repository behavior required for review revisions."""

    async def create(self, revision: ReviewRevision) -> ReviewRevision:
        """Persist revision."""
        ...

    async def list_by_document(self, document_id: uuid.UUID) -> list[ReviewRevision]:
        """Return revisions."""
        ...


class ReviewDecisionRepositoryProtocol(Protocol):
    """Repository behavior required for decisions."""

    async def create(self, decision: ReviewDecision) -> ReviewDecision:
        """Persist decision."""
        ...

    async def list_by_document(self, document_id: uuid.UUID) -> list[ReviewDecision]:
        """Return decisions."""
        ...


class ReviewUnitOfWork(Protocol):
    """Unit of Work contract for document review."""

    extracted_documents: ExtractedDocumentRepositoryProtocol
    extracted_fields: ExtractedFieldRepositoryProtocol
    validation_issues: ValidationIssueRepositoryProtocol
    document_reviews: DocumentReviewRepositoryProtocol
    review_revisions: ReviewRevisionRepositoryProtocol
    review_decisions: ReviewDecisionRepositoryProtocol
    customers: Any
    vendors: Any
    products: Any
    hsn_codes: Any
    sac_codes: Any
    gst_registrations: Any
    sales_invoices: Any
    purchase_invoices: Any

    async def __aenter__(self) -> "ReviewUnitOfWork":
        """Enter transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit transaction."""
        ...


UnitOfWorkFactory = Callable[[], ReviewUnitOfWork]


class DocumentReviewService:
    """Validate extracted business data and coordinate human review."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
        validation_pipeline: BusinessValidationPipeline | None = None,
    ) -> None:
        """Initialize dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._validation_pipeline = validation_pipeline or BusinessValidationPipeline()

    async def validate(self, document_id: uuid.UUID) -> DocumentValidationResponse:
        """Validate extracted document data."""
        async with self._unit_of_work_factory() as uow:
            extracted_document = await self._get_extracted_document(uow, document_id)
            lookup = RepositoryMasterDataLookup(uow)
            issues = await self._validation_pipeline.validate(
                extracted_document,
                lookup,
            )
            persisted_issues = [
                await uow.validation_issues.create(issue) for issue in issues
            ]
            review = await self._get_or_create_review(uow, document_id)
            await self._event_dispatcher.dispatch(
                ValidationCompletedEvent(
                    document_id=document_id,
                    business_id=extracted_document.business_id,
                    issue_count=len(persisted_issues),
                )
            )
            await uow.commit()
            return await self._response(
                uow,
                document_id=document_id,
                business_id=extracted_document.business_id,
                review=review,
                issues=persisted_issues,
            )

    async def get_validation(
        self,
        document_id: uuid.UUID,
    ) -> DocumentValidationResponse:
        """Return validation and review state."""
        async with self._unit_of_work_factory() as uow:
            extracted_document = await self._get_extracted_document(uow, document_id)
            review = await uow.document_reviews.get_by_document_id(document_id)
            if review is None:
                raise DocumentReviewNotFoundException("Document review was not found")
            issues = await uow.validation_issues.list_by_document(document_id)
            response = await self._response(
                uow,
                document_id=document_id,
                business_id=extracted_document.business_id,
                review=review,
                issues=issues,
            )
            await uow.commit()
            return response

    async def review(
        self,
        document_id: uuid.UUID,
        request: DocumentReviewRequest,
        *,
        reviewed_by: uuid.UUID,
    ) -> DocumentValidationResponse:
        """Apply human review decision and optional corrections."""
        async with self._unit_of_work_factory() as uow:
            extracted_document = await self._get_extracted_document(uow, document_id)
            review = await self._get_or_create_review(uow, document_id)
            for correction in request.corrections:
                old_value = self._field_value(extracted_document, correction.field_name)
                revision = await uow.review_revisions.create(
                    ReviewRevision(
                        document_id=document_id,
                        field_name=correction.field_name,
                        old_value=old_value,
                        new_value=correction.new_value,
                        changed_by=reviewed_by,
                        reason=correction.reason,
                    )
                )
                field = await uow.extracted_fields.create(
                    ExtractedField(
                        extracted_document_id=extracted_document.id,
                        document_id=document_id,
                        field_name=correction.field_name,
                        field_value=correction.new_value,
                        confidence=Decimal("100.00"),
                        source=ExtractedFieldSource.VALIDATION,
                        page_number=1,
                        bounding_box=None,
                    )
                )
                extracted_document.fields.append(field)
                _ = revision
            issues = await uow.validation_issues.list_by_document(document_id)
            error_count = sum(
                1
                for issue in issues
                if issue.severity == ValidationSeverity.ERROR and not issue.resolved
            )
            review.review_status = self._status_for_decision(request.decision)
            review.reviewed_by = reviewed_by
            review.reviewed_at = utc_now()
            review.review_notes = request.notes
            review.ready_for_automation = (
                request.decision == ReviewDecisionType.APPROVE and error_count == 0
            )
            decision = await uow.review_decisions.create(
                ReviewDecision(
                    document_id=document_id,
                    decision=request.decision,
                    decided_by=reviewed_by,
                    notes=request.notes,
                )
            )
            _ = decision
            await self._publish_review_event(
                document_id=document_id,
                business_id=extracted_document.business_id,
                reviewed_by=reviewed_by,
                decision=request.decision,
                ready_for_automation=review.ready_for_automation,
            )
            await uow.commit()
            return await self._response(
                uow,
                document_id=document_id,
                business_id=extracted_document.business_id,
                review=review,
                issues=issues,
            )

    async def list_pending(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[DocumentReviewResponse]:
        """List pending document reviews."""
        async with self._unit_of_work_factory() as uow:
            page = await uow.document_reviews.list_pending(
                business_id=business_id,
                pagination=pagination,
            )
            await uow.commit()
        params = pagination or PaginationParams()
        return Page.create(
            items=[DocumentReviewResponse.model_validate(item) for item in page.items],
            total=page.meta.total,
            params=params,
        )

    async def _get_extracted_document(
        self,
        uow: ReviewUnitOfWork,
        document_id: uuid.UUID,
    ) -> ExtractedDocument:
        """Return extracted document or raise."""
        extracted_document = await uow.extracted_documents.get_by_document_id(
            document_id
        )
        if extracted_document is None:
            raise DocumentReviewValidationException(
                "Document extraction is required before validation"
            )
        return extracted_document

    async def _get_or_create_review(
        self,
        uow: ReviewUnitOfWork,
        document_id: uuid.UUID,
    ) -> DocumentReview:
        """Return existing review or create pending review."""
        review = await uow.document_reviews.get_by_document_id(document_id)
        if review is not None:
            return review
        return await uow.document_reviews.create(
            DocumentReview(
                document_id=document_id,
                review_status=ReviewStatus.PENDING,
                ready_for_automation=False,
            )
        )

    async def _response(
        self,
        uow: ReviewUnitOfWork,
        *,
        document_id: uuid.UUID,
        business_id: uuid.UUID,
        review: DocumentReview,
        issues: list[ValidationIssue],
    ) -> DocumentValidationResponse:
        """Build aggregate response."""
        revisions = await uow.review_revisions.list_by_document(document_id)
        decisions = await uow.review_decisions.list_by_document(document_id)
        return DocumentValidationResponse(
            document_id=document_id,
            business_id=business_id,
            issues=issues,
            review=review,
            revisions=revisions,
            decisions=decisions,
            ready_for_automation=review.ready_for_automation,
        )

    def _field_value(
        self,
        extracted_document: ExtractedDocument,
        field_name: str,
    ) -> str | None:
        """Return latest field value."""
        for field in reversed(extracted_document.fields):
            if field.field_name == field_name:
                return field.field_value
        return None

    def _status_for_decision(self, decision: ReviewDecisionType) -> ReviewStatus:
        """Map decision to review status."""
        if decision == ReviewDecisionType.APPROVE:
            return ReviewStatus.APPROVED
        if decision == ReviewDecisionType.REJECT:
            return ReviewStatus.REJECTED
        return ReviewStatus.CORRECTION_REQUESTED

    async def _publish_review_event(
        self,
        *,
        document_id: uuid.UUID,
        business_id: uuid.UUID,
        reviewed_by: uuid.UUID,
        decision: ReviewDecisionType,
        ready_for_automation: bool,
    ) -> None:
        """Publish review decision events."""
        if decision == ReviewDecisionType.APPROVE:
            await self._event_dispatcher.dispatch(
                ReviewApprovedEvent(document_id, business_id, reviewed_by)
            )
        elif decision == ReviewDecisionType.REJECT:
            await self._event_dispatcher.dispatch(
                ReviewRejectedEvent(document_id, business_id, reviewed_by)
            )
        else:
            await self._event_dispatcher.dispatch(
                CorrectionRequestedEvent(document_id, business_id, reviewed_by)
            )
        if ready_for_automation:
            await self._event_dispatcher.dispatch(
                DocumentReadyForAutomationEvent(document_id, business_id)
            )


class RepositoryMasterDataLookup:
    """Master-data lookup adapter over existing repositories."""

    def __init__(self, uow: ReviewUnitOfWork) -> None:
        """Initialize lookup."""
        self._uow = uow

    async def customer_exists(self, business_id: uuid.UUID, name: str) -> bool:
        """Return whether customer exists by search."""
        page = await self._uow.customers.list_business_customers(business_id)
        return any(item.name.lower() == name.lower() for item in page.items)

    async def vendor_exists(self, business_id: uuid.UUID, name: str) -> bool:
        """Return whether vendor exists by search."""
        page = await self._uow.vendors.list_by_business(business_id)
        return any(item.name.lower() == name.lower() for item in page.items)

    async def product_exists(self, business_id: uuid.UUID, description: str) -> bool:
        """Return whether product exists by search."""
        page = await self._uow.products.search(
            business_id=business_id,
            query=description,
        )
        return bool(page.items)

    async def hsn_exists(self, code: str) -> bool:
        """Return whether HSN code exists."""
        return await self._uow.hsn_codes.get_by_code(code) is not None

    async def sac_exists(self, code: str) -> bool:
        """Return whether SAC code exists."""
        return await self._uow.sac_codes.get_by_code(code) is not None

    async def gst_registration_exists(self, gstin: str) -> bool:
        """Return whether GST registration exists."""
        return await self._uow.gst_registrations.get_by_gstin(gstin) is not None

    async def sales_invoice_exists(
        self,
        business_id: uuid.UUID,
        invoice_number: str,
    ) -> bool:
        """Return whether sales invoice exists."""
        return (
            await self._uow.sales_invoices.get_by_invoice_number(
                business_id=business_id,
                invoice_number=invoice_number,
            )
            is not None
        )

    async def purchase_invoice_exists(
        self,
        business_id: uuid.UUID,
        invoice_number: str,
    ) -> bool:
        """Return whether purchase invoice exists."""
        return (
            await self._uow.purchase_invoices.get_by_invoice_number(
                business_id=business_id,
                invoice_number=invoice_number,
            )
            is not None
        )
