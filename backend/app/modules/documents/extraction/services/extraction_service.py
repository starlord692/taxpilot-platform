"""Document field extraction service."""

import uuid
from collections.abc import Callable
from typing import Protocol

from app.common.events import EventDispatcher
from app.modules.documents.extraction.events import (
    ExtractionCompletedEvent,
    ExtractionFailedEvent,
    ReviewRequiredEvent,
)
from app.modules.documents.extraction.exceptions import (
    ExtractionFailedException,
    ExtractionNotFoundException,
    ExtractionValidationException,
)
from app.modules.documents.extraction.extractors import (
    AIExtractionProvider,
    MockAIProvider,
    RuleBasedExtractor,
)
from app.modules.documents.extraction.extractors.types import ExtractedValue
from app.modules.documents.extraction.models import (
    ExtractedDocument,
    ExtractedField,
    ExtractionReview,
    ExtractionRunStatus,
)
from app.modules.documents.extraction.schemas import (
    ExtractDocumentRequest,
    ExtractedDocumentResponse,
)
from app.modules.documents.extraction.validators import ExtractionFieldValidator
from app.modules.documents.models import Document, DocumentType, OCRResult


class DocumentRepositoryProtocol(Protocol):
    """Repository behavior required for documents."""

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        """Return document by UUID."""
        ...


class OCRResultRepositoryProtocol(Protocol):
    """Repository behavior required for OCR results."""

    async def list_by_document(self, document_id: uuid.UUID) -> list[OCRResult]:
        """Return OCR results for a document."""
        ...


class ExtractedDocumentRepositoryProtocol(Protocol):
    """Repository behavior required for extracted documents."""

    async def create(self, extracted_document: ExtractedDocument) -> ExtractedDocument:
        """Create extraction summary."""
        ...

    async def get_by_document_id(
        self,
        document_id: uuid.UUID,
    ) -> ExtractedDocument | None:
        """Return extraction summary by document UUID."""
        ...


class ExtractedFieldRepositoryProtocol(Protocol):
    """Repository behavior required for extracted fields."""

    async def create(self, extracted_field: ExtractedField) -> ExtractedField:
        """Create extracted field."""
        ...


class ExtractionReviewRepositoryProtocol(Protocol):
    """Repository behavior required for extraction reviews."""

    async def create(self, review: ExtractionReview) -> ExtractionReview:
        """Create extraction review."""
        ...


class ExtractionUnitOfWork(Protocol):
    """Unit of Work contract for document extraction."""

    documents: DocumentRepositoryProtocol
    ocr_results: OCRResultRepositoryProtocol
    extracted_documents: ExtractedDocumentRepositoryProtocol
    extracted_fields: ExtractedFieldRepositoryProtocol
    extraction_reviews: ExtractionReviewRepositoryProtocol

    async def __aenter__(self) -> "ExtractionUnitOfWork":
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


UnitOfWorkFactory = Callable[[], ExtractionUnitOfWork]


class DocumentExtractionService:
    """Convert OCR text into structured document extraction output."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
        rule_extractor: RuleBasedExtractor | None = None,
        ai_provider: AIExtractionProvider | None = None,
        validator: ExtractionFieldValidator | None = None,
    ) -> None:
        """Initialize dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._rule_extractor = rule_extractor or RuleBasedExtractor()
        self._ai_provider = ai_provider or MockAIProvider()
        self._validator = validator or ExtractionFieldValidator()

    async def extract(
        self,
        document_id: uuid.UUID,
        request: ExtractDocumentRequest,
    ) -> ExtractedDocumentResponse:
        """Extract structured fields from document OCR text."""
        async with self._unit_of_work_factory() as uow:
            document = await self._get_document(uow, document_id)
            ocr_results = await uow.ocr_results.list_by_document(document_id)
            if not ocr_results:
                await self._event_dispatcher.dispatch(
                    ExtractionFailedEvent(
                        document_id=document.id,
                        business_id=document.business_id,
                        reason="OCR results are required before extraction",
                    )
                )
                raise ExtractionValidationException(
                    "OCR results are required before extraction"
                )
            existing = await uow.extracted_documents.get_by_document_id(document_id)
            if existing is not None:
                await uow.commit()
                return ExtractedDocumentResponse.model_validate(existing)

            text = self._combine_ocr_text(ocr_results)
            document_type = self._classify_document(document, text)
            try:
                fields = self._rule_extractor.extract(text, document_type)
                if request.use_ai:
                    fields.extend(
                        await self._ai_provider.extract(
                            text=text,
                            document_type=document_type,
                        )
                    )
                validation = self._validator.validate(fields)
                status = (
                    ExtractionRunStatus.REVIEW_REQUIRED
                    if validation.review_required
                    else ExtractionRunStatus.COMPLETED
                )
                extracted_document = await uow.extracted_documents.create(
                    ExtractedDocument(
                        document_id=document.id,
                        business_id=document.business_id,
                        document_type=document_type,
                        overall_confidence=validation.overall_confidence,
                        status=status,
                        review_required=validation.review_required,
                    )
                )
                for extracted_value in validation.fields:
                    field = await uow.extracted_fields.create(
                        self._build_field(extracted_document, extracted_value)
                    )
                    extracted_document.fields.append(field)
                if validation.review_required:
                    review = await uow.extraction_reviews.create(
                        ExtractionReview(
                            extracted_document_id=extracted_document.id,
                            reason="; ".join(validation.issues)
                            or "Low confidence extraction",
                        )
                    )
                    extracted_document.reviews.append(review)
                    await self._event_dispatcher.dispatch(
                        ReviewRequiredEvent(
                            document_id=document.id,
                            business_id=document.business_id,
                            reason=review.reason,
                        )
                    )
                await self._event_dispatcher.dispatch(
                    ExtractionCompletedEvent(
                        document_id=document.id,
                        business_id=document.business_id,
                    )
                )
                await uow.commit()
                return ExtractedDocumentResponse.model_validate(extracted_document)
            except Exception as exc:
                await self._event_dispatcher.dispatch(
                    ExtractionFailedEvent(
                        document_id=document.id,
                        business_id=document.business_id,
                        reason=str(exc),
                    )
                )
                if isinstance(exc, ExtractionValidationException):
                    raise
                raise ExtractionFailedException(
                    "Document extraction failed",
                    details={"reason": str(exc)},
                ) from exc

    async def get(self, document_id: uuid.UUID) -> ExtractedDocumentResponse:
        """Return extraction output for a document."""
        async with self._unit_of_work_factory() as uow:
            extracted_document = await uow.extracted_documents.get_by_document_id(
                document_id
            )
            if extracted_document is None:
                raise ExtractionNotFoundException("Document extraction was not found")
            await uow.commit()
            return ExtractedDocumentResponse.model_validate(extracted_document)

    async def _get_document(
        self,
        uow: ExtractionUnitOfWork,
        document_id: uuid.UUID,
    ) -> Document:
        """Return document or raise validation exception."""
        document = await uow.documents.get_by_id(document_id)
        if document is None:
            raise ExtractionValidationException("Document was not found")
        return document

    def _combine_ocr_text(self, ocr_results: list[OCRResult]) -> str:
        """Combine OCR pages into a single text body."""
        ordered = sorted(ocr_results, key=lambda result: result.page_number)
        return "\n".join(result.raw_text for result in ordered if result.raw_text)

    def _classify_document(self, document: Document, text: str) -> DocumentType:
        """Classify document while respecting known document type."""
        if document.document_type != DocumentType.UNKNOWN:
            return document.document_type
        return self._rule_extractor.classify(text)

    def _build_field(
        self,
        extracted_document: ExtractedDocument,
        extracted_value: ExtractedValue,
    ) -> ExtractedField:
        """Build persistent extracted field."""
        return ExtractedField(
            extracted_document_id=extracted_document.id,
            document_id=extracted_document.document_id,
            field_name=extracted_value.field_name,
            field_value=extracted_value.field_value,
            confidence=extracted_value.confidence,
            source=extracted_value.source,
            page_number=extracted_value.page_number,
            bounding_box=None,
        )
