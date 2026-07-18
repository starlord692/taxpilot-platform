"""Tests for document field extraction engine."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Self, cast

import pytest
from fastapi.testclient import TestClient

from app.common.events import Event, EventDispatcher
from app.common.models.abstract.timestamp import utc_now
from app.main import create_app
from app.modules.documents.extraction.api.dependencies import (
    get_document_extraction_service,
    get_extraction_unit_of_work,
)
from app.modules.documents.extraction.events import (
    ExtractionCompletedEvent,
    ReviewRequiredEvent,
)
from app.modules.documents.extraction.models import (
    ExtractedDocument,
    ExtractedField,
    ExtractionReview,
    ExtractionRunStatus,
)
from app.modules.documents.extraction.schemas import ExtractDocumentRequest
from app.modules.documents.extraction.services import (
    DocumentExtractionService,
    ExtractionUnitOfWork,
)
from app.modules.documents.models import (
    Document,
    DocumentType,
    ExtractionStatus,
    OCRResult,
)
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus

HTTP_FORBIDDEN = 403
HTTP_OK = 200


class CapturingEventDispatcher(EventDispatcher):
    """Event dispatcher that captures events."""

    def __init__(self) -> None:
        """Initialize captured events."""
        super().__init__()
        self.events: list[Event] = []

    async def dispatch(self, event: Event) -> None:
        """Capture dispatched event."""
        self.events.append(event)
        await super().dispatch(event)


class FakeMembershipRepository:
    """Fake business membership repository."""

    def __init__(self, *, is_member: bool = True) -> None:
        """Initialize membership response."""
        self.is_member_result = is_member

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return configured membership response."""
        _ = business_id
        _ = user_id
        return self.is_member_result


@dataclass
class FakeDocumentRepository:
    """Fake document repository."""

    documents: list[Document]

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        """Return document by UUID."""
        return next(
            (document for document in self.documents if document.id == document_id),
            None,
        )


@dataclass
class FakeOCRResultRepository:
    """Fake OCR result repository."""

    results: list[OCRResult]

    async def list_by_document(self, document_id: uuid.UUID) -> list[OCRResult]:
        """Return OCR results by document UUID."""
        return [
            result for result in self.results if result.document_id == document_id
        ]


@dataclass
class FakeExtractedDocumentRepository:
    """Fake extracted document repository."""

    records: list[ExtractedDocument] = field(default_factory=list)

    async def create(self, extracted_document: ExtractedDocument) -> ExtractedDocument:
        """Create extracted document."""
        if extracted_document.id is None:
            extracted_document.id = uuid.uuid4()
        self.records.append(extracted_document)
        return extracted_document

    async def get_by_document_id(
        self,
        document_id: uuid.UUID,
    ) -> ExtractedDocument | None:
        """Return extracted document by document UUID."""
        return next(
            (record for record in self.records if record.document_id == document_id),
            None,
        )


@dataclass
class FakeExtractedFieldRepository:
    """Fake extracted field repository."""

    records: list[ExtractedField] = field(default_factory=list)

    async def create(self, extracted_field: ExtractedField) -> ExtractedField:
        """Create extracted field."""
        if extracted_field.id is None:
            extracted_field.id = uuid.uuid4()
        self.records.append(extracted_field)
        return extracted_field


@dataclass
class FakeExtractionReviewRepository:
    """Fake extraction review repository."""

    records: list[ExtractionReview] = field(default_factory=list)

    async def create(self, review: ExtractionReview) -> ExtractionReview:
        """Create extraction review."""
        if review.id is None:
            review.id = uuid.uuid4()
        if review.resolved is None:
            review.resolved = False
        self.records.append(review)
        return review


class FakeExtractionUnitOfWork:
    """Fake Unit of Work for extraction tests."""

    def __init__(
        self,
        *,
        document: Document,
        ocr_results: list[OCRResult],
        is_member: bool = True,
    ) -> None:
        """Initialize fake repositories."""
        self.documents = FakeDocumentRepository([document])
        self.ocr_results = FakeOCRResultRepository(ocr_results)
        self.extracted_documents = FakeExtractedDocumentRepository()
        self.extracted_fields = FakeExtractedFieldRepository()
        self.extraction_reviews = FakeExtractionReviewRepository()
        self.business_memberships = FakeMembershipRepository(is_member=is_member)
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        """Enter transaction."""
        self.committed = False
        self.rolled_back = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Rollback on exception or missing commit."""
        _ = exc
        _ = traceback
        if exc_type is not None or not self.committed:
            self.rolled_back = True

    async def commit(self) -> None:
        """Mark transaction committed."""
        self.committed = True


def build_document(
    business_id: uuid.UUID,
    *,
    document_type: DocumentType = DocumentType.UNKNOWN,
) -> Document:
    """Build source document."""
    return Document(
        id=uuid.uuid4(),
        business_id=business_id,
        uploaded_by=uuid.uuid4(),
        original_filename="invoice.pdf",
        mime_type="application/pdf",
        file_size=128,
        storage_path="memory://invoice.pdf",
        checksum="abc",
        document_type=document_type,
        status=ExtractionStatus.OCR_COMPLETED,
        page_count=1,
        uploaded_at=utc_now(),
        processed_at=utc_now(),
    )


def build_ocr(document_id: uuid.UUID, text: str) -> OCRResult:
    """Build OCR result."""
    return OCRResult(
        id=uuid.uuid4(),
        document_id=document_id,
        page_number=1,
        provider="tesseract",
        language="eng",
        raw_text=text,
        confidence_score=Decimal("95.00"),
        processing_time_ms=10,
        created_at=datetime.now(),
    )


def build_user() -> IdentityUser:
    """Build authenticated user."""
    return IdentityUser(
        id=uuid.uuid4(),
        email="owner@example.com",
        first_name="Aarav",
        last_name="Sharma",
        display_name="Aarav Sharma",
        status=UserStatus.ACTIVE,
    )


def build_service_state(
    text: str,
    *,
    document_type: DocumentType = DocumentType.UNKNOWN,
    is_member: bool = True,
) -> tuple[
    uuid.UUID,
    Document,
    FakeExtractionUnitOfWork,
    DocumentExtractionService,
    CapturingEventDispatcher,
]:
    """Build extraction service state."""
    business_id = uuid.uuid4()
    document = build_document(business_id, document_type=document_type)
    uow = FakeExtractionUnitOfWork(
        document=document,
        ocr_results=[build_ocr(document.id, text)],
        is_member=is_member,
    )
    dispatcher = CapturingEventDispatcher()
    service = DocumentExtractionService(
        unit_of_work_factory=lambda: cast(ExtractionUnitOfWork, uow),
        event_dispatcher=dispatcher,
    )
    return business_id, document, uow, service, dispatcher


@pytest.mark.asyncio
async def test_invoice_extraction() -> None:
    """Invoice OCR text is converted into structured fields."""
    business_id, document, _uow, service, dispatcher = build_service_state(
        """
        Sales Invoice
        Invoice No: INV-1001
        Invoice Date: 10/04/2026
        Due Date: 20/04/2026
        Supplier: Aarav Tech
        Customer: Meera Stores
        Supplier GSTIN: 29ABCDE1234F1Z5
        Customer GSTIN: 27ABCDE1234F1Z5
        PAN: ABCDE1234F
        HSN: 998314
        Payment Terms: Net 10
        Subtotal: 1000.00
        CGST: 90.00
        SGST: 90.00
        Grand Total: 1180.00
        Item: Consulting Qty: 1 Unit: 1000 Tax: 18 Total: 1180
        """,
    )

    extraction = await service.extract(document.id, ExtractDocumentRequest())
    fields = {field.field_name: field.field_value for field in extraction.fields}

    assert extraction.business_id == business_id
    assert extraction.document_type == DocumentType.SALES_INVOICE
    assert extraction.status == ExtractionRunStatus.REVIEW_REQUIRED
    assert fields["invoice_number"] == "INV-1001"
    assert fields["supplier_gstin"] == "29ABCDE1234F1Z5"
    assert fields["customer_gstin"] == "27ABCDE1234F1Z5"
    assert "line_items" in fields
    assert isinstance(dispatcher.events[-1], ExtractionCompletedEvent)


@pytest.mark.asyncio
async def test_receipt_extraction_and_review_flag() -> None:
    """Receipt-like text extracts totals and triggers review when fields are missing."""
    _business_id, document, _uow, service, dispatcher = build_service_state(
        "Expense Receipt\nTotal: 499.00\nGSTIN 29ABCDE1234F1Z5",
        document_type=DocumentType.EXPENSE_RECEIPT,
    )

    extraction = await service.extract(
        document.id,
        ExtractDocumentRequest(use_ai=False),
    )

    assert extraction.document_type == DocumentType.EXPENSE_RECEIPT
    assert extraction.review_required is True
    assert extraction.reviews
    assert any(isinstance(event, ReviewRequiredEvent) for event in dispatcher.events)


@pytest.mark.asyncio
async def test_invalid_gstin_pan_and_low_confidence() -> None:
    """Validation flags invalid and low-confidence extraction output."""
    _business_id, document, _uow, service, _dispatcher = build_service_state(
        "Invoice No: X1\nPAN: ABCDE1234F\nGSTIN 99BAD\nTotal: 10.00",
    )

    extraction = await service.extract(document.id, ExtractDocumentRequest())

    assert extraction.review_required is True
    assert extraction.overall_confidence < Decimal("90.00")
    assert any(
        "invalid GSTIN" in review.reason for review in extraction.reviews
    )


@pytest.mark.asyncio
async def test_get_existing_extraction() -> None:
    """Existing extraction output can be retrieved."""
    _business_id, document, _uow, service, _dispatcher = build_service_state(
        "Invoice No: INV-1\nGrand Total: 1.00",
    )
    created = await service.extract(document.id, ExtractDocumentRequest())

    fetched = await service.get(document.id)

    assert fetched.id == created.id


def test_extraction_api_and_business_isolation() -> None:
    """Extraction API exposes endpoints and enforces business isolation."""
    app = create_app(initialize_resources=False)
    business_id, document, uow, service, _dispatcher = build_service_state(
        "Invoice No: INV-1\nGrand Total: 1.00",
    )
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_extraction_unit_of_work] = lambda: uow
    app.dependency_overrides[get_document_extraction_service] = lambda: service

    with TestClient(app) as client:
        extract_response = client.post(
            f"/api/v1/documents/{document.id}/extract",
            params={"business_id": str(business_id)},
            json={"use_ai": True},
        )
        get_response = client.get(
            f"/api/v1/documents/{document.id}/extraction",
            params={"business_id": str(business_id)},
        )
        schema = client.get("/openapi.json").json()

    assert extract_response.status_code == HTTP_OK
    assert get_response.status_code == HTTP_OK
    assert "/api/v1/documents/{document_id}/extract" in schema["paths"]
    assert "/api/v1/documents/{document_id}/extraction" in schema["paths"]

    denied_business_id, _document, denied_uow, denied_service, _events = (
        build_service_state("Invoice No: INV-2\nGrand Total: 2.00", is_member=False)
    )
    app.dependency_overrides[get_extraction_unit_of_work] = lambda: denied_uow
    app.dependency_overrides[get_document_extraction_service] = lambda: denied_service

    with TestClient(app) as client:
        denied_response = client.post(
            f"/api/v1/documents/{document.id}/extract",
            params={"business_id": str(denied_business_id)},
            json={"use_ai": True},
        )

    assert denied_response.status_code == HTTP_FORBIDDEN
