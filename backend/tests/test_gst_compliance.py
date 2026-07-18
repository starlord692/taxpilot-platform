"""Tests for GST Compliance Engine."""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Self, cast

import pytest
from fastapi.testclient import TestClient

from app.common.events import Event, EventDispatcher
from app.main import create_app
from app.modules.expenses.models import (
    Expense,
    ExpenseCategory,
    ExpenseLine,
    ExpenseStatus,
)
from app.modules.gst.compliance.api.dependencies import (
    get_gst_compliance_service,
    get_gst_compliance_unit_of_work,
)
from app.modules.gst.compliance.models import GSTFilingFrequency
from app.modules.gst.compliance.schemas import GSTReportRequest
from app.modules.gst.compliance.services import GSTComplianceService
from app.modules.gst.compliance.services.compliance_service import (
    GSTComplianceUnitOfWork,
)
from app.modules.gst.events import GSTAuditCompletedEvent, GSTReturnGeneratedEvent
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus
from app.modules.purchases.models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseStatus,
)
from app.modules.sales.models import (
    InvoiceStatus,
    SalesInvoice,
    SalesInvoiceLine,
)

HTTP_OK = 200


class CapturingEventDispatcher(EventDispatcher):
    """Event dispatcher that captures events."""

    def __init__(self) -> None:
        """Initialize captured events."""
        super().__init__()
        self.events: list[Event] = []

    async def dispatch(self, event: Event) -> None:
        """Capture and dispatch an event."""
        self.events.append(event)
        await super().dispatch(event)


class FakeMembershipRepository:
    """Fake business membership repository."""

    def __init__(self, *, is_member: bool = True) -> None:
        """Initialize membership state."""
        self.is_member_result = is_member

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return configured membership state."""
        _ = business_id
        _ = user_id
        return self.is_member_result


@dataclass
class FakeComplianceRepository:
    """Fake GST compliance read repository."""

    sales: list[SalesInvoice]
    purchases: list[PurchaseInvoice]
    expenses: list[Expense]

    async def list_sales(
        self,
        *,
        business_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[SalesInvoice]:
        """Return filtered sales."""
        return [
            invoice
            for invoice in self.sales
            if invoice.business_id == business_id
            and start_date <= invoice.invoice_date <= end_date
        ]

    async def list_purchases(
        self,
        *,
        business_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[PurchaseInvoice]:
        """Return filtered purchases."""
        return [
            purchase
            for purchase in self.purchases
            if purchase.business_id == business_id
            and start_date <= purchase.invoice_date <= end_date
        ]

    async def list_expenses(
        self,
        *,
        business_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[Expense]:
        """Return filtered expenses."""
        return [
            expense
            for expense in self.expenses
            if expense.business_id == business_id
            and start_date <= expense.expense_date <= end_date
        ]


class FakeComplianceUnitOfWork:
    """Fake Unit of Work for compliance tests."""

    def __init__(
        self,
        repository: FakeComplianceRepository,
        *,
        is_member: bool = True,
    ) -> None:
        """Initialize fake repositories."""
        self.gst_compliance = repository
        self.business_memberships = FakeMembershipRepository(is_member=is_member)
        self.committed = False

    async def __aenter__(self) -> Self:
        """Enter fake transaction."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit fake transaction."""
        _ = exc_type
        _ = exc
        _ = traceback

    async def commit(self) -> None:
        """Mark transaction committed."""
        self.committed = True


def build_sales_invoice(business_id: uuid.UUID, invoice_date: date) -> SalesInvoice:
    """Build sales invoice with GST component breakdown."""
    invoice_id = uuid.uuid4()
    return SalesInvoice(
        id=invoice_id,
        business_id=business_id,
        customer_id=uuid.uuid4(),
        invoice_number="INV-001",
        invoice_date=invoice_date,
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("1000.00"),
        discount_amount=Decimal("0.00"),
        taxable_amount=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=invoice_id,
                description="Consulting",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1000.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("90.00"),
                sgst_amount=Decimal("90.00"),
                igst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("1180.00"),
            )
        ],
    )


def build_purchase_invoice(
    business_id: uuid.UUID,
    invoice_date: date,
) -> PurchaseInvoice:
    """Build purchase invoice with GST component breakdown."""
    purchase_id = uuid.uuid4()
    return PurchaseInvoice(
        id=purchase_id,
        business_id=business_id,
        supplier_id=uuid.uuid4(),
        purchase_number="PUR-001",
        invoice_number="SUP-001",
        invoice_date=invoice_date,
        status=PurchaseStatus.APPROVED,
        subtotal=Decimal("500.00"),
        tax_amount=Decimal("90.00"),
        total_amount=Decimal("590.00"),
        lines=[
            PurchaseInvoiceLine(
                id=uuid.uuid4(),
                purchase_invoice_id=purchase_id,
                description="Laptop",
                quantity=Decimal("1.00"),
                unit_cost=Decimal("500.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("45.00"),
                sgst_amount=Decimal("45.00"),
                igst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("590.00"),
            )
        ],
    )


def build_expense(business_id: uuid.UUID, expense_date: date) -> Expense:
    """Build expense with GST component breakdown."""
    expense_id = uuid.uuid4()
    return Expense(
        id=expense_id,
        business_id=business_id,
        expense_number="EXP-001",
        expense_date=expense_date,
        category=ExpenseCategory.SOFTWARE,
        status=ExpenseStatus.APPROVED,
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("18.00"),
        total_amount=Decimal("118.00"),
        attachment_count=0,
        lines=[
            ExpenseLine(
                id=uuid.uuid4(),
                expense_id=expense_id,
                description="Cloud hosting",
                quantity=Decimal("1.00"),
                unit_cost=Decimal("100.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("9.00"),
                sgst_amount=Decimal("9.00"),
                igst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("118.00"),
            )
        ],
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
    *,
    is_member: bool = True,
) -> tuple[
    uuid.UUID,
    FakeComplianceUnitOfWork,
    GSTComplianceService,
    CapturingEventDispatcher,
]:
    """Build service and fake source data."""
    business_id = uuid.uuid4()
    repository = FakeComplianceRepository(
        sales=[
            build_sales_invoice(business_id, date(2026, 4, 10)),
            build_sales_invoice(uuid.uuid4(), date(2026, 4, 12)),
        ],
        purchases=[build_purchase_invoice(business_id, date(2026, 4, 11))],
        expenses=[build_expense(business_id, date(2026, 4, 12))],
    )
    uow = FakeComplianceUnitOfWork(repository, is_member=is_member)
    dispatcher = CapturingEventDispatcher()
    service = GSTComplianceService(
        unit_of_work_factory=lambda: cast(GSTComplianceUnitOfWork, uow),
        event_dispatcher=dispatcher,
    )
    return business_id, uow, service, dispatcher


@pytest.mark.asyncio
async def test_generate_monthly_gstr1_and_hsn_summary() -> None:
    """Compliance service generates monthly GSTR-1 and HSN summary."""
    business_id, uow, service, dispatcher = build_service_state()

    report = await service.generate_gstr1(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    assert report.period.financial_year == "2026-2027"
    assert report.b2b.taxable_value == Decimal("1000.00")
    assert report.b2b.tax_amount == Decimal("180.00")
    assert report.document_summary["sales_invoices"] == 1
    assert report.hsn_summary[0].hsn_code == "UNMAPPED"
    assert uow.committed is True
    assert isinstance(dispatcher.events[0], GSTReturnGeneratedEvent)


@pytest.mark.asyncio
async def test_generate_quarterly_gstr3b_and_itc() -> None:
    """Compliance service supports quarterly GSTR-3B and ITC summaries."""
    business_id, _uow, service, _dispatcher = build_service_state()

    report = await service.generate_gstr3b(
        GSTReportRequest(
            business_id=business_id,
            tax_period="2026-Q1",
            filing_frequency=GSTFilingFrequency.QUARTERLY,
        )
    )
    itc = await service.generate_itc_report(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    assert report.outward_taxable_supplies.tax_amount == Decimal("180.00")
    assert report.input_tax_credit.tax_amount == Decimal("108.00")
    assert report.net_gst_payable == Decimal("72.00")
    assert itc.eligible_itc.tax_amount == Decimal("108.00")


@pytest.mark.asyncio
async def test_generate_audit_report_detects_mismatched_tax() -> None:
    """Audit report detects missing and mismatched GST values."""
    business_id, uow, service, dispatcher = build_service_state()
    report = await service.generate_audit_report(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    assert report.issue_count == 0
    assert isinstance(dispatcher.events[-1], GSTAuditCompletedEvent)

    bad_invoice = build_sales_invoice(business_id, date(2026, 4, 15))
    bad_invoice.tax_amount = Decimal("10.00")
    uow.gst_compliance.sales.append(bad_invoice)
    bad_report = await service.generate_audit_report(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    assert any(issue.code == "mismatched_tax" for issue in bad_report.issues)


@pytest.mark.asyncio
async def test_csv_export_and_business_isolation() -> None:
    """Compliance exports CSV and filters documents by business."""
    business_id, _uow, service, _dispatcher = build_service_state()

    report = await service.generate_sales_summary(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )
    csv_output = service.export_csv(report)

    assert "summary.tax_amount" in csv_output
    assert "180.00" in csv_output


def test_gst_compliance_api_and_openapi() -> None:
    """Compliance API exposes requested endpoints."""
    app = create_app(initialize_resources=False)
    business_id, uow, service, _dispatcher = build_service_state()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_gst_compliance_unit_of_work] = lambda: uow
    app.dependency_overrides[get_gst_compliance_service] = lambda: service

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/gst/compliance/gstr1",
            params={"business_id": str(business_id), "tax_period": "2026-04"},
        )
        csv_response = client.get(
            "/api/v1/gst/compliance/hsn",
            params={
                "business_id": str(business_id),
                "tax_period": "2026-04",
                "export_format": "csv",
            },
        )
        schema = client.get("/openapi.json").json()

    assert response.status_code == HTTP_OK
    assert response.json()["data"]["b2b"]["tax_amount"] == "180.00"
    assert csv_response.status_code == HTTP_OK
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "/api/v1/gst/compliance/gstr1" in schema["paths"]
    assert "/api/v1/gst/compliance/gstr3b" in schema["paths"]
    assert "/api/v1/gst/compliance/itc" in schema["paths"]
    assert "/api/v1/gst/compliance/hsn" in schema["paths"]
    assert "/api/v1/gst/compliance/audit" in schema["paths"]
