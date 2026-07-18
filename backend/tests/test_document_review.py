"""Tests for document validation and human review engine."""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Self, cast

import pytest
from fastapi.testclient import TestClient

from app.common.events import Event, EventDispatcher
from app.common.models.abstract.timestamp import utc_now
from app.common.pagination import Page, PaginationParams
from app.main import create_app
from app.modules.documents.extraction.models import (
    ExtractedDocument,
    ExtractedField,
    ExtractedFieldSource,
    ExtractionRunStatus,
)
from app.modules.documents.models import DocumentType
from app.modules.documents.review.api.dependencies import (
    get_document_review_service,
    get_review_unit_of_work,
)
from app.modules.documents.review.events import (
    CorrectionRequestedEvent,
    DocumentReadyForAutomationEvent,
    ReviewApprovedEvent,
    ReviewRejectedEvent,
    ValidationCompletedEvent,
)
from app.modules.documents.review.models import (
    DocumentReview,
    ReviewDecision,
    ReviewDecisionType,
    ReviewRevision,
    ReviewStatus,
    ValidationCategory,
    ValidationIssue,
    ValidationSeverity,
)
from app.modules.documents.review.schemas import DocumentReviewRequest
from app.modules.documents.review.services import (
    DocumentReviewService,
    ReviewUnitOfWork,
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
class NamedRecord:
    """Simple named master-data record."""

    name: str


@dataclass
class FakeExtractedDocumentRepository:
    """Fake extracted document repository."""

    records: list[ExtractedDocument]

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
class FakeValidationIssueRepository:
    """Fake validation issue repository."""

    records: list[ValidationIssue] = field(default_factory=list)

    async def create(self, issue: ValidationIssue) -> ValidationIssue:
        """Create validation issue."""
        if issue.id is None:
            issue.id = uuid.uuid4()
        if issue.resolved is None:
            issue.resolved = False
        self.records.append(issue)
        return issue

    async def list_by_document(self, document_id: uuid.UUID) -> list[ValidationIssue]:
        """Return validation issues for a document."""
        return [issue for issue in self.records if issue.document_id == document_id]


@dataclass
class FakeDocumentReviewRepository:
    """Fake document review repository."""

    records: list[DocumentReview] = field(default_factory=list)
    extracted_documents: list[ExtractedDocument] = field(default_factory=list)

    async def create(self, review: DocumentReview) -> DocumentReview:
        """Create document review."""
        if review.id is None:
            review.id = uuid.uuid4()
        if review.review_status is None:
            review.review_status = ReviewStatus.PENDING
        if review.ready_for_automation is None:
            review.ready_for_automation = False
        self.records.append(review)
        return review

    async def get_by_document_id(self, document_id: uuid.UUID) -> DocumentReview | None:
        """Return document review by document UUID."""
        return next(
            (review for review in self.records if review.document_id == document_id),
            None,
        )

    async def list_pending(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
    ) -> Page[DocumentReview]:
        """Return pending reviews for a business."""
        params = pagination or PaginationParams()
        document_ids = {
            record.document_id
            for record in self.extracted_documents
            if record.business_id == business_id
        }
        items = [
            review
            for review in self.records
            if review.document_id in document_ids
            and review.review_status == ReviewStatus.PENDING
        ]
        return Page.create(
            items=items[params.offset : params.offset + params.limit],
            total=len(items),
            params=params,
        )


@dataclass
class FakeReviewRevisionRepository:
    """Fake review revision repository."""

    records: list[ReviewRevision] = field(default_factory=list)

    async def create(self, revision: ReviewRevision) -> ReviewRevision:
        """Create review revision."""
        if revision.id is None:
            revision.id = uuid.uuid4()
        if revision.changed_at is None:
            revision.changed_at = utc_now()
        self.records.append(revision)
        return revision

    async def list_by_document(self, document_id: uuid.UUID) -> list[ReviewRevision]:
        """Return revisions for a document."""
        return [
            revision for revision in self.records if revision.document_id == document_id
        ]


@dataclass
class FakeReviewDecisionRepository:
    """Fake review decision repository."""

    records: list[ReviewDecision] = field(default_factory=list)

    async def create(self, decision: ReviewDecision) -> ReviewDecision:
        """Create review decision."""
        if decision.id is None:
            decision.id = uuid.uuid4()
        if decision.decided_at is None:
            decision.decided_at = utc_now()
        self.records.append(decision)
        return decision

    async def list_by_document(self, document_id: uuid.UUID) -> list[ReviewDecision]:
        """Return review decisions for a document."""
        return [
            decision for decision in self.records if decision.document_id == document_id
        ]


class FakeCustomerRepository:
    """Fake customer repository."""

    async def list_business_customers(
        self,
        business_id: uuid.UUID,
    ) -> Page[NamedRecord]:
        """Return no customers."""
        _ = business_id
        return Page.create(items=[], total=0, params=PaginationParams())


class FakeVendorRepository:
    """Fake vendor repository."""

    async def list_by_business(self, business_id: uuid.UUID) -> Page[NamedRecord]:
        """Return no vendors."""
        _ = business_id
        return Page.create(items=[], total=0, params=PaginationParams())


class FakeProductRepository:
    """Fake product repository."""

    async def search(self, *, business_id: uuid.UUID, query: str) -> Page[NamedRecord]:
        """Return no products."""
        _ = business_id
        _ = query
        return Page.create(items=[], total=0, params=PaginationParams())


class FakeCodeRepository:
    """Fake HSN/SAC code repository."""

    async def get_by_code(self, code: str) -> object | None:
        """Return no code."""
        _ = code
        return None


class FakeGSTRegistrationRepository:
    """Fake GST registration repository."""

    async def get_by_gstin(self, gstin: str) -> object | None:
        """Return no GST registration."""
        _ = gstin
        return None


class FakeInvoiceRepository:
    """Fake invoice repository."""

    def __init__(self, duplicate_invoice_number: str | None = None) -> None:
        """Initialize duplicate invoice state."""
        self.duplicate_invoice_number = duplicate_invoice_number

    async def get_by_invoice_number(
        self,
        *,
        business_id: uuid.UUID,
        invoice_number: str,
    ) -> object | None:
        """Return an object when invoice is configured as duplicate."""
        _ = business_id
        if invoice_number == self.duplicate_invoice_number:
            return object()
        return None


class FakeReviewUnitOfWork:
    """Fake Unit of Work for document review tests."""

    def __init__(
        self,
        extracted_document: ExtractedDocument,
        *,
        is_member: bool = True,
        duplicate_invoice_number: str | None = None,
    ) -> None:
        """Initialize fake repositories."""
        self.extracted_documents = FakeExtractedDocumentRepository(
            [extracted_document]
        )
        self.extracted_fields = FakeExtractedFieldRepository()
        self.validation_issues = FakeValidationIssueRepository()
        self.document_reviews = FakeDocumentReviewRepository(
            extracted_documents=[extracted_document]
        )
        self.review_revisions = FakeReviewRevisionRepository()
        self.review_decisions = FakeReviewDecisionRepository()
        self.business_memberships = FakeMembershipRepository(is_member=is_member)
        self.customers = FakeCustomerRepository()
        self.vendors = FakeVendorRepository()
        self.products = FakeProductRepository()
        self.hsn_codes = FakeCodeRepository()
        self.sac_codes = FakeCodeRepository()
        self.gst_registrations = FakeGSTRegistrationRepository()
        self.sales_invoices = FakeInvoiceRepository(duplicate_invoice_number)
        self.purchase_invoices = FakeInvoiceRepository()
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
        """Rollback fake transaction on exception or missing commit."""
        _ = exc
        _ = traceback
        if exc_type is not None or not self.committed:
            self.rolled_back = True

    async def commit(self) -> None:
        """Mark transaction committed."""
        self.committed = True


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


def build_extracted_document(
    business_id: uuid.UUID,
    fields: dict[str, str | list[str]],
) -> ExtractedDocument:
    """Build extracted document with fields."""
    document_id = uuid.uuid4()
    extracted_document = ExtractedDocument(
        id=uuid.uuid4(),
        document_id=document_id,
        business_id=business_id,
        document_type=DocumentType.PURCHASE_INVOICE,
        overall_confidence=Decimal("90.00"),
        status=ExtractionRunStatus.REVIEW_REQUIRED,
        review_required=True,
        fields=[],
        reviews=[],
    )
    for name, raw_value in fields.items():
        values = raw_value if isinstance(raw_value, list) else [raw_value]
        for value in values:
            extracted_document.fields.append(
                ExtractedField(
                    id=uuid.uuid4(),
                    extracted_document_id=extracted_document.id,
                    document_id=document_id,
                    field_name=name,
                    field_value=value,
                    confidence=Decimal("90.00"),
                    source=ExtractedFieldSource.RULE,
                    page_number=1,
                )
            )
    return extracted_document


def build_service_state(
    fields: dict[str, str | list[str]],
    *,
    is_member: bool = True,
    duplicate_invoice_number: str | None = None,
) -> tuple[
    uuid.UUID,
    FakeReviewUnitOfWork,
    DocumentReviewService,
    CapturingEventDispatcher,
]:
    """Build review service state."""
    business_id = uuid.uuid4()
    extracted_document = build_extracted_document(business_id, fields)
    uow = FakeReviewUnitOfWork(
        extracted_document,
        is_member=is_member,
        duplicate_invoice_number=duplicate_invoice_number,
    )
    dispatcher = CapturingEventDispatcher()
    service = DocumentReviewService(
        unit_of_work_factory=lambda: cast(ReviewUnitOfWork, uow),
        event_dispatcher=dispatcher,
    )
    return business_id, uow, service, dispatcher


@pytest.mark.asyncio
async def test_validation_detects_duplicate_and_format_issues() -> None:
    """Validation detects duplicate invoices plus GST and PAN errors."""
    _business_id, uow, service, dispatcher = build_service_state(
        {
            "invoice_number": "INV-1001",
            "supplier_gstin": "bad-gstin",
            "pan": "bad-pan",
            "subtotal": "100.00",
            "tax_amount": "18.00",
            "cgst": "9.00",
            "sgst": "9.00",
            "grand_total": "118.00",
        },
        duplicate_invoice_number="INV-1001",
    )

    response = await service.validate(uow.extracted_documents.records[0].document_id)

    categories = {issue.category for issue in response.issues}
    assert ValidationCategory.DUPLICATE in categories
    assert ValidationCategory.GST in categories
    assert ValidationCategory.PAN in categories
    assert any(
        issue.severity == ValidationSeverity.ERROR for issue in response.issues
    )
    assert isinstance(dispatcher.events[-1], ValidationCompletedEvent)


@pytest.mark.asyncio
async def test_master_data_matching_warnings() -> None:
    """Missing master-data records are reported as matching warnings."""
    _business_id, uow, service, _dispatcher = build_service_state(
        {
            "invoice_number": "INV-2001",
            "grand_total": "100.00",
            "customer_name": "Unknown Customer",
            "supplier_name": "Unknown Vendor",
            "line_items": ["Unknown Product"],
            "hsn": "998314",
            "sac": "998315",
            "gstin": "29ABCDE1234F1Z5",
        }
    )

    response = await service.validate(uow.extracted_documents.records[0].document_id)

    matching_fields = {
        issue.field_name
        for issue in response.issues
        if issue.category == ValidationCategory.MATCHING
    }
    assert {
        "customer_name",
        "supplier_name",
        "line_items",
        "hsn",
        "sac",
        "gstin",
    }.issubset(matching_fields)
    assert all(
        issue.severity == ValidationSeverity.WARNING for issue in response.issues
    )


@pytest.mark.asyncio
async def test_manual_correction_tracks_revision_and_requests_correction() -> None:
    """Manual corrections append fields and preserve immutable revision history."""
    _business_id, uow, service, dispatcher = build_service_state(
        {"invoice_number": "INV-3001", "grand_total": "100.00"}
    )
    document_id = uow.extracted_documents.records[0].document_id
    user_id = uuid.uuid4()
    await service.validate(document_id)

    response = await service.review(
        document_id,
        DocumentReviewRequest(
            decision=ReviewDecisionType.REQUEST_CORRECTION,
            notes="Correct supplier GSTIN",
            corrections=[
                {
                    "field_name": "supplier_gstin",
                    "new_value": "29ABCDE1234F1Z5",
                    "reason": "Confirmed from supplier document",
                }
            ],
        ),
        reviewed_by=user_id,
    )

    assert response.review is not None
    assert response.review.review_status == ReviewStatus.CORRECTION_REQUESTED
    assert response.revisions[0].field_name == "supplier_gstin"
    assert response.revisions[0].old_value is None
    assert uow.extracted_fields.records[0].source == ExtractedFieldSource.VALIDATION
    assert isinstance(dispatcher.events[-1], CorrectionRequestedEvent)


@pytest.mark.asyncio
async def test_approval_rejection_and_automation_flag() -> None:
    """Approval sets readiness only when there are no unresolved error issues."""
    _business_id, uow, service, dispatcher = build_service_state(
        {
            "invoice_number": "INV-4001",
            "subtotal": "100.00",
            "tax_amount": "18.00",
            "cgst": "9.00",
            "sgst": "9.00",
            "grand_total": "118.00",
        }
    )
    document_id = uow.extracted_documents.records[0].document_id
    reviewer_id = uuid.uuid4()
    await service.validate(document_id)

    approved = await service.review(
        document_id,
        DocumentReviewRequest(decision=ReviewDecisionType.APPROVE),
        reviewed_by=reviewer_id,
    )
    rejected = await service.review(
        document_id,
        DocumentReviewRequest(decision=ReviewDecisionType.REJECT),
        reviewed_by=reviewer_id,
    )

    assert approved.ready_for_automation is True
    assert rejected.ready_for_automation is False
    assert any(isinstance(event, ReviewApprovedEvent) for event in dispatcher.events)
    assert any(isinstance(event, ReviewRejectedEvent) for event in dispatcher.events)
    assert any(
        isinstance(event, DocumentReadyForAutomationEvent)
        for event in dispatcher.events
    )


def test_review_api_and_business_isolation() -> None:
    """Review API exposes endpoints and enforces business isolation."""
    app = create_app(initialize_resources=False)
    business_id, uow, service, _dispatcher = build_service_state(
        {"invoice_number": "INV-5001", "grand_total": "100.00"}
    )
    document_id = uow.extracted_documents.records[0].document_id
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_review_unit_of_work] = lambda: uow
    app.dependency_overrides[get_document_review_service] = lambda: service

    with TestClient(app) as client:
        validate_response = client.post(
            f"/api/v1/documents/{document_id}/validate",
            params={"business_id": str(business_id)},
        )
        get_response = client.get(
            f"/api/v1/documents/{document_id}/validation",
            params={"business_id": str(business_id)},
        )
        review_response = client.post(
            f"/api/v1/documents/{document_id}/review",
            params={"business_id": str(business_id)},
            json={"decision": "approve", "notes": "Looks good"},
        )
        pending_response = client.get(
            "/api/v1/documents/review/pending",
            params={"business_id": str(business_id)},
        )
        schema = client.get("/openapi.json").json()

    assert validate_response.status_code == HTTP_OK
    assert get_response.status_code == HTTP_OK
    assert review_response.status_code == HTTP_OK
    assert pending_response.status_code == HTTP_OK
    assert review_response.json()["data"]["ready_for_automation"] is True
    assert "/api/v1/documents/{document_id}/validate" in schema["paths"]
    assert "/api/v1/documents/{document_id}/review" in schema["paths"]
    assert "/api/v1/documents/review/pending" in schema["paths"]

    _denied_business_id, denied_uow, denied_service, _events = build_service_state(
        {"invoice_number": "INV-6001", "grand_total": "100.00"},
        is_member=False,
    )
    app.dependency_overrides[get_review_unit_of_work] = lambda: denied_uow
    app.dependency_overrides[get_document_review_service] = lambda: denied_service

    with TestClient(app) as client:
        denied_response = client.post(
            f"/api/v1/documents/{document_id}/validate",
            params={"business_id": str(business_id)},
        )

    assert denied_response.status_code == HTTP_FORBIDDEN
