"""Tests for ERP document automation engine."""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Self, cast

import pytest
from fastapi.testclient import TestClient

from app.common.events import Event, EventDispatcher
from app.common.exceptions import TaxPilotException
from app.common.models.abstract.timestamp import utc_now
from app.main import create_app
from app.modules.documents.automation.api.dependencies import (
    get_automation_unit_of_work,
    get_document_automation_service,
)
from app.modules.documents.automation.events import (
    AutomationCompletedEvent,
    AutomationFailedEvent,
    AutomationStartedEvent,
)
from app.modules.documents.automation.exceptions import (
    AutomationConflictException,
    AutomationMappingException,
)
from app.modules.documents.automation.models import (
    AutomationRun,
    AutomationState,
    AutomationType,
)
from app.modules.documents.automation.services import (
    AutomationUnitOfWork,
    DocumentAutomationService,
)
from app.modules.documents.automation.strategies import (
    ExpenseAutomationStrategy,
    PurchaseAutomationStrategy,
    SalesAutomationStrategy,
)
from app.modules.documents.extraction.models import (
    ExtractedDocument,
    ExtractedField,
    ExtractedFieldSource,
    ExtractionRunStatus,
)
from app.modules.documents.models import DocumentType
from app.modules.documents.review.models import ReviewStatus
from app.modules.documents.review.schemas import (
    DocumentReviewResponse,
    DocumentValidationResponse,
)
from app.modules.expenses.models import ExpenseCategory, ExpenseStatus
from app.modules.expenses.schemas import ExpenseResponse
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus
from app.modules.purchases.models import PurchaseStatus
from app.modules.purchases.schemas import PurchaseInvoiceResponse
from app.modules.sales.models import InvoiceStatus
from app.modules.sales.schemas import InvoiceResponse

HTTP_FORBIDDEN = 403
HTTP_OK = 200
EXPECTED_RETRY_CALLS = 2


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


class DomainFailure(TaxPilotException):
    """Expected fake ERP service failure."""

    error_code = "domain.failure"


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
class FakeAutomationRunRepository:
    """In-memory automation run repository."""

    records: list[AutomationRun] = field(default_factory=list)

    async def create_started(
        self,
        *,
        document_id: uuid.UUID,
        business_id: uuid.UUID,
        automation_type: AutomationType,
        idempotency_key: str,
    ) -> AutomationRun:
        """Create running automation metadata."""
        run = AutomationRun(
            id=uuid.uuid4(),
            document_id=document_id,
            business_id=business_id,
            automation_type=automation_type,
            idempotency_key=idempotency_key,
            status=AutomationState.RUNNING,
            started_at=utc_now(),
            retry_count=0,
        )
        self.records.append(run)
        return run

    async def get_by_document_id(
        self,
        document_id: uuid.UUID,
    ) -> AutomationRun | None:
        """Return latest run for document."""
        matches = [run for run in self.records if run.document_id == document_id]
        return matches[-1] if matches else None

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> AutomationRun | None:
        """Return run by idempotency key."""
        return next(
            (run for run in self.records if run.idempotency_key == idempotency_key),
            None,
        )

    async def get_running_for_document(
        self,
        document_id: uuid.UUID,
    ) -> AutomationRun | None:
        """Return running run for document."""
        return next(
            (
                run
                for run in self.records
                if run.document_id == document_id
                and run.status == AutomationState.RUNNING
            ),
            None,
        )

    async def mark_completed(
        self,
        run: AutomationRun,
        *,
        erp_record_type: str,
        erp_record_id: uuid.UUID,
    ) -> AutomationRun:
        """Mark run completed."""
        run.status = AutomationState.COMPLETED
        run.erp_record_type = erp_record_type
        run.erp_record_id = erp_record_id
        run.completed_at = utc_now()
        return run

    async def mark_failed(
        self,
        run: AutomationRun,
        *,
        reason: str,
    ) -> AutomationRun:
        """Mark run failed."""
        run.status = AutomationState.FAILED
        run.failure_reason = reason
        run.completed_at = utc_now()
        run.retry_count += 1
        return run


@dataclass
class FakeExtractedDocumentRepository:
    """Fake extracted document repository."""

    extracted_document: ExtractedDocument

    async def get_by_document_id(
        self,
        document_id: uuid.UUID,
    ) -> ExtractedDocument | None:
        """Return extracted document."""
        if self.extracted_document.document_id == document_id:
            return self.extracted_document
        return None


class FakeAutomationUnitOfWork:
    """Fake Unit of Work for automation tests."""

    def __init__(
        self,
        extracted_document: ExtractedDocument,
        *,
        is_member: bool = True,
    ) -> None:
        """Initialize repositories."""
        self.automation_runs = FakeAutomationRunRepository()
        self.extracted_documents = FakeExtractedDocumentRepository(extracted_document)
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
        """Mark rollback on failure."""
        _ = exc
        _ = traceback
        if exc_type is not None or not self.committed:
            self.rolled_back = True

    async def commit(self) -> None:
        """Mark committed."""
        self.committed = True


class FakeReviewService:
    """Fake review service returning ready validation."""

    def __init__(self, *, business_id: uuid.UUID, ready: bool = True) -> None:
        """Initialize review state."""
        self.business_id = business_id
        self.ready = ready

    async def get_validation(
        self,
        document_id: uuid.UUID,
    ) -> DocumentValidationResponse:
        """Return validation response."""
        return DocumentValidationResponse(
            document_id=document_id,
            business_id=self.business_id,
            issues=[],
            review=DocumentReviewResponse(
                id=uuid.uuid4(),
                document_id=document_id,
                review_status=ReviewStatus.APPROVED,
                ready_for_automation=self.ready,
            ),
            ready_for_automation=self.ready,
        )


class FakeSalesService:
    """Fake sales service."""

    def __init__(self, *, fail_once: bool = False) -> None:
        """Initialize service state."""
        self.calls = 0
        self.fail_once = fail_once

    async def create_invoice(self, request: object) -> InvoiceResponse:
        """Create fake sales invoice."""
        self.calls += 1
        if self.fail_once:
            self.fail_once = False
            raise DomainFailure("Sales failed")
        data = cast(Any, request)
        return InvoiceResponse(
            id=uuid.uuid4(),
            business_id=data.business_id,
            customer_id=data.customer_id,
            invoice_number=data.invoice_number,
            invoice_date=data.invoice_date,
            due_date=data.due_date,
            status=InvoiceStatus.DRAFT,
            subtotal=data.subtotal,
            discount_amount=data.discount_amount,
            taxable_amount=data.taxable_amount,
            tax_amount=data.tax_amount,
            total_amount=data.total_amount,
            notes=data.notes,
            lines=[],
            payments=[],
        )


class FakePurchaseService:
    """Fake purchase service."""

    def __init__(self) -> None:
        """Initialize service state."""
        self.calls = 0

    async def create_purchase(
        self,
        request: object,
        *,
        business_id: uuid.UUID,
    ) -> PurchaseInvoiceResponse:
        """Create fake purchase invoice."""
        self.calls += 1
        data = cast(Any, request)
        return PurchaseInvoiceResponse(
            id=uuid.uuid4(),
            business_id=business_id,
            supplier_id=data.supplier_id,
            purchase_number="PUR-1",
            invoice_number=data.invoice_number,
            invoice_date=data.invoice_date,
            due_date=data.due_date,
            status=PurchaseStatus.DRAFT,
            total_amount=data.total_amount,
            attachment_count=0,
            subtotal=data.subtotal,
            tax_amount=data.tax_amount,
            notes=data.notes,
            supplier=None,
            lines=[],
        )


class FakeExpenseService:
    """Fake expense service."""

    def __init__(self) -> None:
        """Initialize service state."""
        self.calls = 0

    async def create_expense(
        self,
        request: object,
        *,
        business_id: uuid.UUID,
    ) -> ExpenseResponse:
        """Create fake expense."""
        self.calls += 1
        data = cast(Any, request)
        return ExpenseResponse(
            id=uuid.uuid4(),
            business_id=business_id,
            vendor_id=data.vendor_id,
            expense_number="EXP-1",
            expense_date=data.expense_date,
            category=data.category,
            status=ExpenseStatus.DRAFT,
            total_amount=data.total_amount,
            attachment_count=0,
            description=data.description,
            subtotal=data.subtotal,
            tax_amount=data.tax_amount,
            notes=data.notes,
            vendor=None,
            lines=[],
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


def build_extracted_document(
    business_id: uuid.UUID,
    document_type: DocumentType,
    *,
    overrides: dict[str, str] | None = None,
) -> ExtractedDocument:
    """Build extracted document with automation-ready fields."""
    document_id = uuid.uuid4()
    fields = {
        "customer_id": str(uuid.uuid4()),
        "supplier_id": str(uuid.uuid4()),
        "vendor_id": str(uuid.uuid4()),
        "invoice_number": "INV-1001",
        "invoice_date": "2026-04-01",
        "due_date": "2026-04-30",
        "expense_date": "2026-04-01",
        "expense_category": ExpenseCategory.SOFTWARE.value,
        "line_description": "Consulting",
        "description": "Consulting",
        "quantity": "1.00",
        "unit_price": "1000.00",
        "unit_cost": "1000.00",
        "tax_rate": "18.00",
        "discount": "0.00",
        "subtotal": "1000.00",
        "tax_amount": "180.00",
        "grand_total": "1180.00",
        "line_total": "1180.00",
    }
    fields.update(overrides or {})
    extracted_document = ExtractedDocument(
        id=uuid.uuid4(),
        document_id=document_id,
        business_id=business_id,
        document_type=document_type,
        overall_confidence=Decimal("95.00"),
        status=ExtractionRunStatus.COMPLETED,
        review_required=False,
        fields=[],
        reviews=[],
    )
    for name, value in fields.items():
        extracted_document.fields.append(
            ExtractedField(
                id=uuid.uuid4(),
                extracted_document_id=extracted_document.id,
                document_id=document_id,
                field_name=name,
                field_value=value,
                confidence=Decimal("95.00"),
                source=ExtractedFieldSource.VALIDATION,
                page_number=1,
            )
        )
    return extracted_document


def build_service_state(
    document_type: DocumentType,
    *,
    overrides: dict[str, str] | None = None,
    is_member: bool = True,
    sales_service: FakeSalesService | None = None,
) -> tuple[
    uuid.UUID,
    FakeAutomationUnitOfWork,
    DocumentAutomationService,
    CapturingEventDispatcher,
    FakeSalesService,
    FakePurchaseService,
    FakeExpenseService,
]:
    """Build automation service state."""
    business_id = uuid.uuid4()
    extracted_document = build_extracted_document(
        business_id,
        document_type,
        overrides=overrides,
    )
    uow = FakeAutomationUnitOfWork(extracted_document, is_member=is_member)
    dispatcher = CapturingEventDispatcher()
    sales = sales_service or FakeSalesService()
    purchase = FakePurchaseService()
    expense = FakeExpenseService()
    service = DocumentAutomationService(
        unit_of_work_factory=lambda: cast(AutomationUnitOfWork, uow),
        review_service=cast(Any, FakeReviewService(business_id=business_id)),
        strategies=[
            SalesAutomationStrategy(sales_service=cast(Any, sales)),
            PurchaseAutomationStrategy(purchase_service=cast(Any, purchase)),
            ExpenseAutomationStrategy(expense_service=cast(Any, expense)),
        ],
        event_dispatcher=dispatcher,
    )
    return business_id, uow, service, dispatcher, sales, purchase, expense


@pytest.mark.asyncio
async def test_sales_automation_and_idempotency() -> None:
    """Sales automation delegates to SalesService and reuses completed runs."""
    business_id, uow, service, dispatcher, sales, _purchase, _expense = (
        build_service_state(DocumentType.SALES_INVOICE)
    )
    document_id = uow.extracted_documents.extracted_document.document_id

    first = await service.automate(
        document_id,
        business_id=business_id,
        idempotency_key="sales-key-1",
    )
    second = await service.automate(
        document_id,
        business_id=business_id,
        idempotency_key="sales-key-1",
    )

    assert first.run.status == AutomationState.COMPLETED
    assert first.run.erp_record_type == "sales_invoice"
    assert second.reused_existing is True
    assert sales.calls == 1
    assert any(isinstance(event, AutomationStartedEvent) for event in dispatcher.events)
    assert any(
        isinstance(event, AutomationCompletedEvent) for event in dispatcher.events
    )


@pytest.mark.asyncio
async def test_purchase_and_expense_strategy_selection() -> None:
    """Automation selects PurchaseService or ExpenseService by document type."""
    purchase_state = build_service_state(DocumentType.PURCHASE_INVOICE)
    business_id, uow, service, _events, _sales, purchase, _expense = purchase_state
    await service.automate(
        uow.extracted_documents.extracted_document.document_id,
        business_id=business_id,
        idempotency_key="purchase-key-1",
    )

    expense_state = build_service_state(DocumentType.EXPENSE_RECEIPT)
    expense_business, expense_uow, expense_service, _d, _s, _p, expense = expense_state
    await expense_service.automate(
        expense_uow.extracted_documents.extracted_document.document_id,
        business_id=expense_business,
        idempotency_key="expense-key-1",
    )

    assert purchase.calls == 1
    assert expense.calls == 1


@pytest.mark.asyncio
async def test_duplicate_concurrent_request_rejected() -> None:
    """A running automation blocks concurrent document automation."""
    business_id, uow, service, _events, _sales, _purchase, _expense = (
        build_service_state(DocumentType.SALES_INVOICE)
    )
    document_id = uow.extracted_documents.extracted_document.document_id
    await uow.automation_runs.create_started(
        document_id=document_id,
        business_id=business_id,
        automation_type=AutomationType.SALES,
        idempotency_key="running-key",
    )

    with pytest.raises(AutomationConflictException):
        await service.automate(
            document_id,
            business_id=business_id,
            idempotency_key="another-key",
        )


@pytest.mark.asyncio
async def test_mapper_validation_failure_marks_run_failed() -> None:
    """Mapper failure prevents ERP service call and marks run failed."""
    business_id, uow, service, dispatcher, sales, _purchase, _expense = (
        build_service_state(
            DocumentType.SALES_INVOICE,
            overrides={"line_description": ""},
        )
    )
    document_id = uow.extracted_documents.extracted_document.document_id

    with pytest.raises(AutomationMappingException):
        await service.automate(
            document_id,
            business_id=business_id,
            idempotency_key="bad-map-key",
        )

    run = await uow.automation_runs.get_by_idempotency_key("bad-map-key")
    assert run is not None
    assert run.status == AutomationState.FAILED
    assert sales.calls == 0
    assert any(isinstance(event, AutomationFailedEvent) for event in dispatcher.events)


@pytest.mark.asyncio
async def test_domain_failure_can_retry_with_new_key() -> None:
    """Domain service failure marks failed run and a later retry can succeed."""
    failing_sales = FakeSalesService(fail_once=True)
    business_id, uow, service, _events, sales, _purchase, _expense = (
        build_service_state(
            DocumentType.SALES_INVOICE,
            sales_service=failing_sales,
        )
    )
    document_id = uow.extracted_documents.extracted_document.document_id

    with pytest.raises(DomainFailure):
        await service.automate(
            document_id,
            business_id=business_id,
            idempotency_key="retry-key-1",
        )
    result = await service.automate(
        document_id,
        business_id=business_id,
        idempotency_key="retry-key-2",
    )

    failed = await uow.automation_runs.get_by_idempotency_key("retry-key-1")
    assert failed is not None
    assert failed.retry_count == 1
    assert failed.status == AutomationState.FAILED
    assert result.run.status == AutomationState.COMPLETED
    assert sales.calls == EXPECTED_RETRY_CALLS


def test_automation_api_and_business_isolation() -> None:
    """Automation API exposes endpoints and enforces business isolation."""
    app = create_app(initialize_resources=False)
    business_id, uow, service, _events, _sales, _purchase, _expense = (
        build_service_state(DocumentType.SALES_INVOICE)
    )
    document_id = uow.extracted_documents.extracted_document.document_id
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_automation_unit_of_work] = lambda: uow
    app.dependency_overrides[get_document_automation_service] = lambda: service

    with TestClient(app) as client:
        automate_response = client.post(
            f"/api/v1/documents/{document_id}/automate",
            params={"business_id": str(business_id)},
            json={"idempotency_key": "api-key-1"},
        )
        get_response = client.get(
            f"/api/v1/documents/{document_id}/automation",
            params={"business_id": str(business_id)},
        )
        schema = client.get("/openapi.json").json()

    assert automate_response.status_code == HTTP_OK
    assert get_response.status_code == HTTP_OK
    assert "/api/v1/documents/{document_id}/automate" in schema["paths"]
    assert "/api/v1/documents/{document_id}/automation" in schema["paths"]

    _denied_business_id, denied_uow, denied_service, _e, _s, _p, _x = (
        build_service_state(DocumentType.SALES_INVOICE, is_member=False)
    )
    app.dependency_overrides[get_automation_unit_of_work] = lambda: denied_uow
    app.dependency_overrides[get_document_automation_service] = lambda: denied_service

    with TestClient(app) as client:
        denied_response = client.post(
            f"/api/v1/documents/{document_id}/automate",
            params={"business_id": str(business_id)},
            json={"idempotency_key": "api-key-2"},
        )

    assert denied_response.status_code == HTTP_FORBIDDEN
