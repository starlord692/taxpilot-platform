"""Tests for GST Compliance Engine."""

import csv as py_csv
import io
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Self, cast

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

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
from app.modules.gst.compliance.schemas import (
    GSTAmountSummary,
    GSTReportRequest,
    GSTRReconciliationDiscrepancy,
    GSTRReconciliationReport,
    GSTRReconciliationStatus,
    ReconciliationDataSource,
)
from app.modules.gst.compliance.services import (
    GSTComplianceService,
)
from app.modules.gst.compliance.services import (
    compliance_service as comp_svc_mod,
)
from app.modules.gst.compliance.services.compliance_service import (
    GSTComplianceUnitOfWork,
)
from app.modules.gst.events import (
    GSTAuditCompletedEvent,
    GSTReconciliationCompletedEvent,
    GSTReturnGeneratedEvent,
)
from app.modules.gst.exceptions import (
    GSTComparisonInputValidationException,
    GSTInvalidPeriodException,
)
from app.modules.gst.services.gst_calculation_service import GSTSupplyType
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus
from app.modules.purchases.models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseStatus,
)
from app.modules.sales.models import (
    Customer,
    InvoiceStatus,
    SalesInvoice,
    SalesInvoiceLine,
)

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403


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


def build_utgst_sales_invoice(
    business_id: uuid.UUID,
    invoice_date: date,
    *,
    customer: Customer | None = None,
) -> SalesInvoice:
    """Build intra-UT sales invoice with CGST and UTGST."""
    invoice_id = uuid.uuid4()
    cust_id = customer.id if customer else uuid.uuid4()
    return SalesInvoice(
        id=invoice_id,
        business_id=business_id,
        customer_id=cust_id,
        customer=customer,
        invoice_number="INV-UT-001",
        invoice_date=invoice_date,
        place_of_supply="04",
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
                description="UT Consulting",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1000.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("90.00"),
                sgst_amount=Decimal("0.00"),
                igst_amount=Decimal("0.00"),
                utgst_amount=Decimal("90.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("1180.00"),
            )
        ],
    )


def build_b2c_sales_invoice(
    business_id: uuid.UUID,
    invoice_date: date,
) -> SalesInvoice:
    """Build B2C sales invoice with unregistered customer (no GSTIN)."""
    invoice_id = uuid.uuid4()
    cust = Customer(
        id=uuid.uuid4(),
        business_id=business_id,
        customer_code="CUST-B2C",
        name="Retail Consumer",
        gstin=None,
    )
    return SalesInvoice(
        id=invoice_id,
        business_id=business_id,
        customer_id=cust.id,
        customer=cust,
        invoice_number="INV-B2C-001",
        invoice_date=invoice_date,
        place_of_supply="29",
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("500.00"),
        discount_amount=Decimal("0.00"),
        taxable_amount=Decimal("500.00"),
        tax_amount=Decimal("90.00"),
        total_amount=Decimal("590.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=invoice_id,
                description="Retail Product",
                quantity=Decimal("1.00"),
                unit_price=Decimal("500.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("45.00"),
                sgst_amount=Decimal("45.00"),
                igst_amount=Decimal("0.00"),
                utgst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("590.00"),
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
    assert "/api/v1/gst/compliance/reconciliation" in schema["paths"]


@pytest.mark.asyncio
async def test_generate_gstr1_with_utgst_and_b2b_b2c_segregation() -> None:
    """GSTR-1 report segregates B2B from B2C and accumulates UTGST."""
    business_id, uow, service, _dispatcher = build_service_state()
    ut_invoice = build_utgst_sales_invoice(business_id, date(2026, 4, 15))
    b2c_invoice = build_b2c_sales_invoice(business_id, date(2026, 4, 18))
    uow.gst_compliance.sales.extend([ut_invoice, b2c_invoice])

    report = await service.generate_gstr1(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    assert report.b2b.taxable_value == Decimal("2000.00")
    assert report.b2b.cgst_amount == Decimal("180.00")
    assert report.b2b.sgst_amount == Decimal("90.00")
    assert report.b2b.utgst_amount == Decimal("90.00")
    assert report.b2b.tax_amount == Decimal("360.00")
    assert report.b2b.total_amount == Decimal("2360.00")

    assert report.b2c.taxable_value == Decimal("500.00")
    assert report.b2c.cgst_amount == Decimal("45.00")
    assert report.b2c.sgst_amount == Decimal("45.00")
    assert report.b2c.utgst_amount == Decimal("0.00")
    assert report.b2c.tax_amount == Decimal("90.00")
    assert report.b2c.total_amount == Decimal("590.00")

    expected_invoice_count = 3
    assert report.document_summary["sales_invoices"] == expected_invoice_count


@pytest.mark.asyncio
async def test_generate_audit_report_does_not_flag_utgst_invoice() -> None:
    """Audit report recognizes UTGST and avoids false-positive mismatched_tax."""
    business_id = uuid.uuid4()
    ut_invoice = build_utgst_sales_invoice(business_id, date(2026, 4, 15))
    repository = FakeComplianceRepository(
        sales=[ut_invoice],
        purchases=[],
        expenses=[],
    )
    uow = FakeComplianceUnitOfWork(repository)
    dispatcher = CapturingEventDispatcher()
    service = GSTComplianceService(
        unit_of_work_factory=lambda: cast(GSTComplianceUnitOfWork, uow),
        event_dispatcher=dispatcher,
    )

    report = await service.generate_audit_report(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    assert report.issue_count == 0
    assert not any(issue.code == "mismatched_tax" for issue in report.issues)


@pytest.mark.asyncio
async def test_generate_gstr3b_includes_utgst_in_liability() -> None:
    """GSTR-3B includes UTGST in outward supplies and tax liability."""
    business_id = uuid.uuid4()
    ut_invoice = build_utgst_sales_invoice(business_id, date(2026, 4, 15))
    purchase = build_purchase_invoice(business_id, date(2026, 4, 11))
    repository = FakeComplianceRepository(
        sales=[ut_invoice],
        purchases=[purchase],
        expenses=[],
    )
    uow = FakeComplianceUnitOfWork(repository)
    dispatcher = CapturingEventDispatcher()
    service = GSTComplianceService(
        unit_of_work_factory=lambda: cast(GSTComplianceUnitOfWork, uow),
        event_dispatcher=dispatcher,
    )

    report = await service.generate_gstr3b(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    assert report.outward_taxable_supplies.utgst_amount == Decimal("90.00")
    assert report.outward_taxable_supplies.cgst_amount == Decimal("90.00")
    assert report.tax_liability.utgst_amount == Decimal("90.00")
    assert report.tax_liability.tax_amount == Decimal("180.00")
    assert report.input_tax_credit.tax_amount == Decimal("90.00")
    assert report.net_gst_payable == Decimal("90.00")


@pytest.mark.asyncio
async def test_hsn_summary_includes_utgst() -> None:
    """HSN summary correctly accumulates UTGST component and computes taxable value."""
    business_id = uuid.uuid4()
    ut_invoice = build_utgst_sales_invoice(business_id, date(2026, 4, 15))
    repository = FakeComplianceRepository(
        sales=[ut_invoice],
        purchases=[],
        expenses=[],
    )
    uow = FakeComplianceUnitOfWork(repository)
    service = GSTComplianceService(
        unit_of_work_factory=lambda: cast(GSTComplianceUnitOfWork, uow),
        event_dispatcher=CapturingEventDispatcher(),
    )

    hsn_lines = await service.generate_hsn_summary(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    assert len(hsn_lines) == 1
    assert hsn_lines[0].utgst_amount == Decimal("90.00")
    assert hsn_lines[0].cgst_amount == Decimal("90.00")
    assert hsn_lines[0].sgst_amount == Decimal("0.00")
    assert hsn_lines[0].taxable_value == Decimal("1000.00")
    assert hsn_lines[0].tax_amount == Decimal("180.00")
    assert hsn_lines[0].total_amount == Decimal("1180.00")


@pytest.mark.asyncio
async def test_csv_export_includes_utgst_amount() -> None:
    """CSV export includes summary.utgst_amount field and values."""
    business_id = uuid.uuid4()
    ut_invoice = build_utgst_sales_invoice(business_id, date(2026, 4, 15))
    repository = FakeComplianceRepository(
        sales=[ut_invoice],
        purchases=[],
        expenses=[],
    )
    uow = FakeComplianceUnitOfWork(repository)
    service = GSTComplianceService(
        unit_of_work_factory=lambda: cast(GSTComplianceUnitOfWork, uow),
        event_dispatcher=CapturingEventDispatcher(),
    )

    report = await service.generate_sales_summary(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )
    csv_output = service.export_csv(report)

    assert "summary.utgst_amount" in csv_output
    assert "90.00" in csv_output


@pytest.mark.asyncio
async def test_mixed_rate_invoice_segregates_taxable_and_nil_rated_lines() -> None:
    """Multi-line invoice with taxable and nil-rated items partitions correctly."""
    business_id = uuid.uuid4()
    cust = Customer(
        id=uuid.uuid4(),
        business_id=business_id,
        customer_code="CUST-B2B",
        name="Enterprise Corp",
        gstin="29ABCDE1234F1Z5",
    )
    mixed_invoice_id = uuid.uuid4()
    mixed_invoice = SalesInvoice(
        id=mixed_invoice_id,
        business_id=business_id,
        customer_id=cust.id,
        customer=cust,
        invoice_number="INV-MIXED-001",
        invoice_date=date(2026, 4, 15),
        place_of_supply="29",
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("1400.00"),
        discount_amount=Decimal("0.00"),
        taxable_amount=Decimal("1400.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1580.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=mixed_invoice_id,
                description="Taxable Consulting",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1000.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("90.00"),
                sgst_amount=Decimal("90.00"),
                igst_amount=Decimal("0.00"),
                utgst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("1180.00"),
            ),
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=mixed_invoice_id,
                description="Nil-Rated Grains",
                quantity=Decimal("1.00"),
                unit_price=Decimal("400.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("0.00"),
                cgst_amount=Decimal("0.00"),
                sgst_amount=Decimal("0.00"),
                igst_amount=Decimal("0.00"),
                utgst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("400.00"),
            ),
        ],
    )
    mixed_invoice.lines[0].hsn_code = "998311"
    mixed_invoice.lines[1].hsn_code = "1001"

    repository = FakeComplianceRepository(
        sales=[mixed_invoice],
        purchases=[],
        expenses=[],
    )
    uow = FakeComplianceUnitOfWork(repository)
    service = GSTComplianceService(
        unit_of_work_factory=lambda: cast(GSTComplianceUnitOfWork, uow),
        event_dispatcher=CapturingEventDispatcher(),
    )

    gstr1 = await service.generate_gstr1(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    # Table 4 (B2B): Contains ONLY taxable line portion
    assert gstr1.b2b.taxable_value == Decimal("1000.00")
    assert gstr1.b2b.tax_amount == Decimal("180.00")
    assert gstr1.b2b.cgst_amount == Decimal("90.00")
    assert gstr1.b2b.sgst_amount == Decimal("90.00")

    # Table 8 (Nil-Rated): Contains ONLY nil-rated line portion
    assert gstr1.nil_rated.taxable_value == Decimal("400.00")
    assert gstr1.nil_rated.tax_amount == Decimal("0.00")
    assert gstr1.exempt.taxable_value == Decimal("0.00")

    # Invariant: Total turnover matches exactly
    assert gstr1.b2b.taxable_value + gstr1.nil_rated.taxable_value == Decimal("1400.00")

    # HSN summary contains both distinct lines
    hsn_dict = {line.hsn_code: line for line in gstr1.hsn_summary}
    assert hsn_dict["998311"].taxable_value == Decimal("1000.00")
    assert hsn_dict["998311"].tax_amount == Decimal("180.00")
    assert hsn_dict["1001"].taxable_value == Decimal("400.00")
    assert hsn_dict["1001"].tax_amount == Decimal("0.00")

    # GSTR-3B segregation
    gstr3b = await service.generate_gstr3b(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )
    assert gstr3b.outward_taxable_supplies.taxable_value == Decimal("1000.00")
    assert gstr3b.outward_taxable_supplies.tax_amount == Decimal("180.00")
    assert gstr3b.exempt_supplies.taxable_value == Decimal("400.00")
    assert gstr3b.exempt_supplies.tax_amount == Decimal("0.00")
    assert (
        gstr3b.outward_taxable_supplies.taxable_value
        + gstr3b.exempt_supplies.taxable_value
        == Decimal("1400.00")
    )


@pytest.mark.asyncio
async def test_full_discount_taxable_line_not_nil_or_exempt() -> None:
    """A taxable rate line with 100% discount is never classified as nil or exempt."""
    business_id = uuid.uuid4()
    cust = Customer(
        id=uuid.uuid4(),
        business_id=business_id,
        customer_code="CUST-B2B",
        name="Enterprise Corp",
        gstin="29ABCDE1234F1Z5",
    )
    discount_invoice_id = uuid.uuid4()
    discount_invoice = SalesInvoice(
        id=discount_invoice_id,
        business_id=business_id,
        customer_id=cust.id,
        customer=cust,
        invoice_number="INV-DISC-001",
        invoice_date=date(2026, 4, 15),
        place_of_supply="29",
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("500.00"),
        discount_amount=Decimal("500.00"),
        taxable_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("0.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=discount_invoice_id,
                description="Taxable Software Trial (100% Discounted)",
                quantity=Decimal("1.00"),
                unit_price=Decimal("500.00"),
                discount=Decimal("500.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("0.00"),
                sgst_amount=Decimal("0.00"),
                igst_amount=Decimal("0.00"),
                utgst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("0.00"),
            )
        ],
    )

    repository = FakeComplianceRepository(
        sales=[discount_invoice],
        purchases=[],
        expenses=[],
    )
    uow = FakeComplianceUnitOfWork(repository)
    service = GSTComplianceService(
        unit_of_work_factory=lambda: cast(GSTComplianceUnitOfWork, uow),
        event_dispatcher=CapturingEventDispatcher(),
    )

    gstr1 = await service.generate_gstr1(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    # Stays under B2B with 0 amounts, NOT classified as Nil-Rated or Exempt
    assert gstr1.b2b.taxable_value == Decimal("0.00")
    assert gstr1.b2b.tax_amount == Decimal("0.00")
    assert gstr1.nil_rated.taxable_value == Decimal("0.00")
    assert gstr1.exempt.taxable_value == Decimal("0.00")

    gstr3b = await service.generate_gstr3b(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )
    assert gstr3b.outward_taxable_supplies.taxable_value == Decimal("0.00")
    assert gstr3b.exempt_supplies.taxable_value == Decimal("0.00")


@pytest.mark.asyncio
async def test_explicit_exempt_supply_classified_into_exempt_summary() -> None:
    """Explicitly exempt supplies populate GSTR-1 and GSTR-3B exempt summaries."""
    business_id = uuid.uuid4()
    cust = Customer(
        id=uuid.uuid4(),
        business_id=business_id,
        customer_code="CUST-B2B",
        name="Hospital Clinic",
        gstin="29ABCDE1234F1Z5",
    )
    exempt_invoice_id = uuid.uuid4()
    exempt_invoice = SalesInvoice(
        id=exempt_invoice_id,
        business_id=business_id,
        customer_id=cust.id,
        customer=cust,
        invoice_number="INV-EXEMPT-001",
        invoice_date=date(2026, 4, 15),
        place_of_supply="29",
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("800.00"),
        discount_amount=Decimal("0.00"),
        taxable_amount=Decimal("800.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("800.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=exempt_invoice_id,
                description="Healthcare Professional Fee",
                quantity=Decimal("1.00"),
                unit_price=Decimal("600.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("0.00"),
                cgst_amount=Decimal("0.00"),
                sgst_amount=Decimal("0.00"),
                igst_amount=Decimal("0.00"),
                utgst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("600.00"),
            ),
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=exempt_invoice_id,
                description="Fresh Milk",
                quantity=Decimal("1.00"),
                unit_price=Decimal("200.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("0.00"),
                cgst_amount=Decimal("0.00"),
                sgst_amount=Decimal("0.00"),
                igst_amount=Decimal("0.00"),
                utgst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("200.00"),
            ),
        ],
    )
    exempt_invoice.lines[0].supply_type = GSTSupplyType.EXEMPT
    exempt_invoice.lines[1].supply_type = GSTSupplyType.NIL_RATED

    repository = FakeComplianceRepository(
        sales=[exempt_invoice],
        purchases=[],
        expenses=[],
    )
    uow = FakeComplianceUnitOfWork(repository)
    service = GSTComplianceService(
        unit_of_work_factory=lambda: cast(GSTComplianceUnitOfWork, uow),
        event_dispatcher=CapturingEventDispatcher(),
    )

    gstr1 = await service.generate_gstr1(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    # GSTR-1 Table 8 correctly separates exempt and nil-rated
    assert gstr1.exempt.taxable_value == Decimal("600.00")
    assert gstr1.exempt.tax_amount == Decimal("0.00")
    assert gstr1.nil_rated.taxable_value == Decimal("200.00")
    assert gstr1.nil_rated.tax_amount == Decimal("0.00")
    assert gstr1.b2b.taxable_value == Decimal("0.00")

    # GSTR-3B Table 3.1(c) aggregates both exempt and nil-rated
    gstr3b = await service.generate_gstr3b(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )
    assert gstr3b.exempt_supplies.taxable_value == Decimal("800.00")
    assert gstr3b.exempt_supplies.tax_amount == Decimal("0.00")
    assert gstr3b.outward_taxable_supplies.taxable_value == Decimal("0.00")


@pytest.mark.asyncio
async def test_generate_reconciliation_fails_closed_when_gstr3b_unprovided() -> None:
    """Reconciliation fails closed with NOT_COMPARABLE when GSTR-3B data is missing."""
    business_id, _uow, service, dispatcher = build_service_state()

    report = await service.generate_reconciliation(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    assert report.status == GSTRReconciliationStatus.NOT_COMPARABLE
    assert report.comparison_source == ReconciliationDataSource.UNPROVIDED
    assert report.is_portal_verified is False
    assert report.is_comparison_performed is False
    assert report.is_outward_compared is False
    assert report.is_itc_compared is False
    assert report.is_outward_matched is False
    assert report.is_itc_matched is False
    assert report.requires_policy_approval is False
    assert report.statutory_determination_claim is False
    assert report.drc01b_risk is False
    assert report.outward_discrepancy is None
    assert report.itc_discrepancy is None
    assert report.turnover_discrepancy is None
    assert report.gstr3b_outward is None
    assert report.itc_gstr3b is None
    assert report.gstr3b_total_turnover is None
    assert len(report.variance_reasons) == 1
    assert "cannot be performed" in report.variance_reasons[0]
    reconciliation_events = [
        event
        for event in dispatcher.events
        if isinstance(event, GSTReconciliationCompletedEvent)
    ]
    assert len(reconciliation_events) == 1
    ev = reconciliation_events[0]
    assert ev.status == GSTRReconciliationStatus.NOT_COMPARABLE.value
    assert ev.is_comparison_performed is False
    assert ev.is_matched is False
    assert ev.comparison_source == "unprovided"
    assert ev.is_portal_verified is False


@pytest.mark.asyncio
async def test_generate_reconciliation_matched_for_clean_returns() -> None:
    """Reconciliation produces MATCHED status with clean matching returns."""
    business_id, _uow, service, dispatcher = build_service_state()

    gstr3b_liability = GSTAmountSummary(
        taxable_value=Decimal("1000.00"),
        cgst_amount=Decimal("90.00"),
        sgst_amount=Decimal("90.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
    )
    gstr3b_itc = GSTAmountSummary(
        taxable_value=Decimal("600.00"),
        cgst_amount=Decimal("54.00"),
        sgst_amount=Decimal("54.00"),
        tax_amount=Decimal("108.00"),
        total_amount=Decimal("708.00"),
    )

    report = await service.generate_reconciliation(
        GSTReportRequest(business_id=business_id, tax_period="2026-04"),
        gstr3b_liability_override=gstr3b_liability,
        gstr3b_itc_override=gstr3b_itc,
    )

    assert report.status == GSTRReconciliationStatus.MATCHED
    assert report.comparison_source == ReconciliationDataSource.USER_SUPPLIED
    assert report.is_portal_verified is False
    assert report.is_comparison_performed is True
    assert report.is_outward_compared is True
    assert report.is_itc_compared is True
    assert report.is_outward_matched is True
    assert report.is_itc_matched is True
    assert report.requires_policy_approval is False
    assert report.statutory_determination_claim is False
    assert report.drc01b_risk is False
    assert report.drc01c_risk is False
    assert report.outward_discrepancy.tax_amount == Decimal("0.00")
    assert report.itc_discrepancy.tax_amount == Decimal("0.00")
    assert report.turnover_discrepancy == Decimal("0.00")
    assert len(report.variance_reasons) == 0
    reconciliation_events = [
        event
        for event in dispatcher.events
        if isinstance(event, GSTReconciliationCompletedEvent)
    ]
    assert len(reconciliation_events) == 1
    ev = reconciliation_events[0]
    assert ev.status == GSTRReconciliationStatus.MATCHED.value
    assert ev.is_comparison_performed is True
    assert ev.is_matched is True
    assert ev.comparison_source == "user_supplied"
    assert ev.is_portal_verified is False


@pytest.mark.asyncio
async def test_generate_reconciliation_detects_drc01b_risk() -> None:
    """Reconciliation identifies CBIC Rule 88C DRC-01B outward risk."""
    business_id = uuid.uuid4()
    high_sales_invoice = build_sales_invoice(business_id, date(2026, 4, 10))
    high_sales_invoice.taxable_amount = Decimal("166666.67")
    high_sales_invoice.tax_amount = Decimal("30000.00")
    high_sales_invoice.total_amount = Decimal("196666.67")
    high_sales_invoice.lines[0].line_total = Decimal("196666.67")
    high_sales_invoice.lines[0].cgst_amount = Decimal("15000.00")
    high_sales_invoice.lines[0].sgst_amount = Decimal("15000.00")
    high_sales_invoice.lines[0].tax_rate = Decimal("18.00")

    repository = FakeComplianceRepository(
        sales=[high_sales_invoice],
        purchases=[],
        expenses=[],
    )
    uow = FakeComplianceUnitOfWork(repository)
    dispatcher = CapturingEventDispatcher()
    service = GSTComplianceService(
        unit_of_work_factory=lambda: cast(GSTComplianceUnitOfWork, uow),
        event_dispatcher=dispatcher,
    )

    gstr3b_liability_override = GSTAmountSummary(
        taxable_value=Decimal("5555.56"),
        cgst_amount=Decimal("500.00"),
        sgst_amount=Decimal("500.00"),
        tax_amount=Decimal("1000.00"),
        total_amount=Decimal("6555.56"),
    )

    report = await service.generate_reconciliation(
        GSTReportRequest(business_id=business_id, tax_period="2026-04"),
        gstr3b_liability_override=gstr3b_liability_override,
    )

    assert report.status == GSTRReconciliationStatus.DRC01B_RISK
    assert report.is_outward_matched is False
    assert report.drc01b_risk is True
    assert report.requires_policy_approval is True
    assert report.statutory_determination_claim is False
    assert report.outward_discrepancy.tax_amount == Decimal("29000.00")
    assert any(
        isinstance(event, GSTReconciliationCompletedEvent)
        and event.status == GSTRReconciliationStatus.DRC01B_RISK.value
        for event in dispatcher.events
    )


@pytest.mark.asyncio
async def test_generate_reconciliation_detects_drc01c_risk() -> None:
    """Reconciliation identifies CBIC Rule 88D DRC-01C excess ITC risk."""
    business_id, _uow, service, dispatcher = build_service_state()
    gstr3b_itc_override = GSTAmountSummary(
        taxable_value=Decimal("200000.00"),
        cgst_amount=Decimal("18000.00"),
        sgst_amount=Decimal("18000.00"),
        tax_amount=Decimal("36000.00"),
        total_amount=Decimal("236000.00"),
    )

    report = await service.generate_reconciliation(
        GSTReportRequest(business_id=business_id, tax_period="2026-04"),
        gstr3b_itc_override=gstr3b_itc_override,
    )

    assert report.status == GSTRReconciliationStatus.DRC01C_RISK
    assert report.is_itc_matched is False
    assert report.drc01c_risk is True
    assert report.requires_policy_approval is True
    assert report.statutory_determination_claim is False
    assert report.itc_discrepancy.tax_amount == Decimal("-35892.00")
    assert any(
        isinstance(event, GSTReconciliationCompletedEvent)
        and event.status == GSTRReconciliationStatus.DRC01C_RISK.value
        for event in dispatcher.events
    )


@pytest.mark.asyncio
async def test_reconciliation_rejects_invalid_tax_period() -> None:
    """Reconciliation strictly validates period format and fails closed."""
    business_id, uow, service, _dispatcher = build_service_state()

    with pytest.raises(GSTInvalidPeriodException) as exc_info_month:
        await service.generate_reconciliation(
            GSTReportRequest(business_id=business_id, tax_period="2026-13")
        )
    assert exc_info_month.value.error_code == "gst.invalid_tax_period"

    with pytest.raises(GSTInvalidPeriodException) as exc_info_invalid:
        await service.generate_reconciliation(
            GSTReportRequest(business_id=business_id, tax_period="invalid-period")
        )
    assert exc_info_invalid.value.error_code == "gst.invalid_tax_period"

    app = create_app(initialize_resources=False)
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_gst_compliance_unit_of_work] = lambda: uow
    app.dependency_overrides[get_gst_compliance_service] = lambda: service

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/gst/compliance/reconciliation",
            params={"business_id": str(business_id), "tax_period": "2026-99"},
        )
        assert response.status_code == HTTP_BAD_REQUEST
        error_data = response.json()
        assert error_data["success"] is False
        assert error_data["data"]["code"] == "gst.invalid_tax_period"


def test_gst_compliance_reconciliation_api_endpoint_and_csv() -> None:
    """Compliance reconciliation API serves JSON/CSV and enforces isolation."""
    app = create_app(initialize_resources=False)
    business_id, uow, service, _dispatcher = build_service_state()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_gst_compliance_unit_of_work] = lambda: uow
    app.dependency_overrides[get_gst_compliance_service] = lambda: service

    with TestClient(app) as client:
        # 1. Unprovided GSTR-3B data returns fail-closed NOT_COMPARABLE
        default_resp = client.get(
            "/api/v1/gst/compliance/reconciliation",
            params={"business_id": str(business_id), "tax_period": "2026-04"},
        )
        assert default_resp.status_code == HTTP_OK
        default_data = default_resp.json()["data"]
        assert default_data["status"] == "not_comparable"
        assert default_data["is_comparison_performed"] is False
        assert default_data["outward_discrepancy"] is None
        assert default_data["itc_discrepancy"] is None
        assert default_data["gstr3b_outward"] is None
        assert default_data["itc_gstr3b"] is None
        assert default_data["turnover_discrepancy"] is None

        # 2. Matching GSTR-3B values produce clean MATCHED status
        matched_resp = client.get(
            "/api/v1/gst/compliance/reconciliation",
            params={
                "business_id": str(business_id),
                "tax_period": "2026-04",
                "gstr3b_taxable_value": "1000.00",
                "gstr3b_tax_amount": "180.00",
                "gstr3b_cgst_amount": "90.00",
                "gstr3b_sgst_amount": "90.00",
                "gstr3b_itc_taxable_value": "600.00",
                "gstr3b_itc_amount": "108.00",
                "gstr3b_itc_cgst_amount": "54.00",
                "gstr3b_itc_sgst_amount": "54.00",
            },
        )
        assert matched_resp.status_code == HTTP_OK
        data = matched_resp.json()["data"]
        assert data["status"] == "matched"
        assert data["is_outward_matched"] is True
        assert data["is_itc_matched"] is True
        assert data["is_comparison_performed"] is True

        # 3. CSV export with matching params
        csv_response = client.get(
            "/api/v1/gst/compliance/reconciliation",
            params={
                "business_id": str(business_id),
                "tax_period": "2026-04",
                "gstr3b_taxable_value": "1000.00",
                "gstr3b_tax_amount": "180.00",
                "gstr3b_cgst_amount": "90.00",
                "gstr3b_sgst_amount": "90.00",
                "gstr3b_itc_taxable_value": "600.00",
                "gstr3b_itc_amount": "108.00",
                "gstr3b_itc_cgst_amount": "54.00",
                "gstr3b_itc_sgst_amount": "54.00",
                "export_format": "csv",
            },
        )
        assert csv_response.status_code == HTTP_OK
        assert csv_response.headers["content-type"].startswith("text/csv")
        csv_text = csv_response.text
        assert "status" in csv_text
        assert "matched" in csv_text

        # 4. Tenant isolation (non-member forbidden)
        uow.business_memberships.is_member_result = False
        forbidden_response = client.get(
            "/api/v1/gst/compliance/reconciliation",
            params={"business_id": str(business_id), "tax_period": "2026-04"},
        )
        assert forbidden_response.status_code == HTTP_FORBIDDEN


def test_csv_export_neutralizes_formula_injection() -> None:
    """CSV export neutralizes formula injection while preserving decimals."""
    _business_id, _uow, service, _dispatcher = build_service_state()

    assert service._sanitize_csv_cell("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert service._sanitize_csv_cell("+1+2") == "'+1+2"
    assert service._sanitize_csv_cell("-@SUM(A1:A10)") == "'-@SUM(A1:A10)"
    assert service._sanitize_csv_cell("@SUM(A1:B10)") == "'@SUM(A1:B10)"
    assert service._sanitize_csv_cell("\tTAB_FORMULA") == "'\tTAB_FORMULA"
    assert service._sanitize_csv_cell("\rCR_FORMULA") == "'\rCR_FORMULA"

    # Valid signed numeric amounts are preserved without single quote prefix
    assert service._sanitize_csv_cell("-35892.00") == "-35892.00"
    assert service._sanitize_csv_cell("+100.50") == "+100.50"
    assert service._sanitize_csv_cell(Decimal("-250.00")) == Decimal("-250.00")


@pytest.mark.asyncio
async def test_audit_report_detects_unclassified_zero_tax_supply() -> None:
    """Audit report flags zero-tax supplies lacking classification metadata."""
    business_id = uuid.uuid4()
    cust = Customer(
        id=uuid.uuid4(),
        business_id=business_id,
        customer_code="CUST-B2B",
        name="Enterprise Corp",
        gstin="29ABCDE1234F1Z5",
    )
    unclass_id = uuid.uuid4()
    unclass_invoice = SalesInvoice(
        id=unclass_id,
        business_id=business_id,
        customer_id=cust.id,
        customer=cust,
        invoice_number="INV-UNCLASS-001",
        invoice_date=date(2026, 4, 15),
        place_of_supply="29",
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("500.00"),
        discount_amount=Decimal("0.00"),
        taxable_amount=Decimal("500.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("500.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=unclass_id,
                description="Unclassified Zero Tax Item",
                quantity=Decimal("1.00"),
                unit_price=Decimal("500.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("0.00"),
                cgst_amount=Decimal("0.00"),
                sgst_amount=Decimal("0.00"),
                igst_amount=Decimal("0.00"),
                utgst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("500.00"),
            )
        ],
    )

    repository = FakeComplianceRepository(
        sales=[unclass_invoice],
        purchases=[],
        expenses=[],
    )
    uow = FakeComplianceUnitOfWork(repository)
    dispatcher = CapturingEventDispatcher()
    service = GSTComplianceService(
        unit_of_work_factory=lambda: cast(GSTComplianceUnitOfWork, uow),
        event_dispatcher=dispatcher,
    )

    report = await service.generate_audit_report(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    assert report.issue_count >= 1
    unclassified_issues = [
        issue for issue in report.issues if issue.code == "unclassified_zero_tax_supply"
    ]
    assert len(unclassified_issues) == 1
    assert unclassified_issues[0].source_id == unclass_id

    # Authoritative metadata (NIL_RATED) prevents audit issue
    unclass_invoice.lines[0].supply_type = GSTSupplyType.NIL_RATED
    clean_report = await service.generate_audit_report(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )
    assert not any(
        issue.code == "unclassified_zero_tax_supply" for issue in clean_report.issues
    )


@pytest.mark.asyncio
async def test_reconciliation_partial_comparison_returns_not_comparable() -> None:
    """Partial return comparison returns NOT_COMPARABLE, never MATCHED."""
    business_id, _uow, service, dispatcher = build_service_state()

    gstr3b_liability = GSTAmountSummary(
        taxable_value=Decimal("1000.00"),
        cgst_amount=Decimal("90.00"),
        sgst_amount=Decimal("90.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
    )

    # Only outward liability provided; ITC unprovided
    report = await service.generate_reconciliation(
        GSTReportRequest(business_id=business_id, tax_period="2026-04"),
        gstr3b_liability_override=gstr3b_liability,
        gstr3b_itc_override=None,
    )

    assert report.status == GSTRReconciliationStatus.NOT_COMPARABLE
    assert report.comparison_source == ReconciliationDataSource.USER_SUPPLIED
    assert report.is_portal_verified is False
    assert report.is_comparison_performed is True
    assert report.is_outward_compared is True
    assert report.is_outward_matched is True
    assert report.is_itc_compared is False
    assert report.is_itc_matched is False
    assert report.itc_discrepancy is None
    assert report.itc_gstr3b is None
    assert report.outward_discrepancy is not None
    assert report.gstr3b_outward is not None
    assert any("ITC data unprovided" in r for r in report.variance_reasons)

    ev = [
        e for e in dispatcher.events
        if isinstance(e, GSTReconciliationCompletedEvent)
    ][0]
    assert ev.status == GSTRReconciliationStatus.NOT_COMPARABLE.value
    assert ev.is_comparison_performed is True
    assert ev.is_matched is False
    assert ev.comparison_source == "user_supplied"


@pytest.mark.asyncio
async def test_reconciliation_detects_component_mismatch_with_equal_aggregate() -> None:
    """Detect component head discrepancies even when aggregate tax matches."""
    business_id, _uow, service, dispatcher = build_service_state()

    # Total is ₹180.00, but all in IGST while books has CGST ₹90.00 + SGST ₹90.00
    mismatched_liability = GSTAmountSummary(
        taxable_value=Decimal("1000.00"),
        cgst_amount=Decimal("0.00"),
        sgst_amount=Decimal("0.00"),
        igst_amount=Decimal("180.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
    )
    gstr3b_itc = GSTAmountSummary(
        taxable_value=Decimal("600.00"),
        cgst_amount=Decimal("54.00"),
        sgst_amount=Decimal("54.00"),
        tax_amount=Decimal("108.00"),
        total_amount=Decimal("708.00"),
    )

    report = await service.generate_reconciliation(
        GSTReportRequest(business_id=business_id, tax_period="2026-04"),
        gstr3b_liability_override=mismatched_liability,
        gstr3b_itc_override=gstr3b_itc,
    )

    assert report.status == GSTRReconciliationStatus.DISCREPANCY_DETECTED
    assert report.is_outward_matched is False
    assert report.is_itc_matched is True
    assert report.outward_discrepancy.tax_amount == Decimal("0.00")
    assert report.outward_discrepancy.cgst_amount == Decimal("90.00")
    assert report.outward_discrepancy.sgst_amount == Decimal("90.00")
    assert report.outward_discrepancy.igst_amount == Decimal("-180.00")
    assert any("Outward IGST discrepancy" in r for r in report.variance_reasons)
    assert any("Outward CGST discrepancy" in r for r in report.variance_reasons)
    assert any("Outward SGST discrepancy" in r for r in report.variance_reasons)

    ev = [
        e for e in dispatcher.events
        if isinstance(e, GSTReconciliationCompletedEvent)
    ][0]
    assert ev.status == GSTRReconciliationStatus.DISCREPANCY_DETECTED.value
    assert ev.is_matched is False


@pytest.mark.asyncio
async def test_reconciliation_service_rejects_malformed_override() -> None:
    """Service directly rejects negative values and contradictory component sums."""
    business_id, _uow, service, _dispatcher = build_service_state()

    # Negative amount in override
    neg_override = GSTAmountSummary(
        taxable_value=Decimal("1000.00"),
        cgst_amount=Decimal("-90.00"),
        sgst_amount=Decimal("90.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("1000.00"),
    )
    with pytest.raises(GSTComparisonInputValidationException) as exc_info_neg:
        await service.generate_reconciliation(
            GSTReportRequest(business_id=business_id, tax_period="2026-04"),
            gstr3b_liability_override=neg_override,
        )
    assert exc_info_neg.value.error_code == "gst.invalid_comparison_input"

    # Contradictory component sum (90 + 90 != 200)
    contradictory_override = GSTAmountSummary(
        taxable_value=Decimal("1000.00"),
        cgst_amount=Decimal("90.00"),
        sgst_amount=Decimal("90.00"),
        tax_amount=Decimal("200.00"),
        total_amount=Decimal("1200.00"),
    )
    with pytest.raises(GSTComparisonInputValidationException) as exc_info_contra:
        await service.generate_reconciliation(
            GSTReportRequest(business_id=business_id, tax_period="2026-04"),
            gstr3b_liability_override=contradictory_override,
        )
    assert exc_info_contra.value.error_code == "gst.invalid_comparison_input"


def test_reconciliation_rejects_negative_comparison_inputs() -> None:
    """API endpoint strictly rejects negative comparison values with 400 Bad Request."""
    app = create_app(initialize_resources=False)
    business_id, uow, service, dispatcher = build_service_state()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_gst_compliance_unit_of_work] = lambda: uow
    app.dependency_overrides[get_gst_compliance_service] = lambda: service

    with TestClient(app) as client:
        # Negative tax amount
        resp_tax = client.get(
            "/api/v1/gst/compliance/reconciliation",
            params={
                "business_id": str(business_id),
                "tax_period": "2026-04",
                "gstr3b_tax_amount": "-50.00",
            },
        )
        assert resp_tax.status_code == HTTP_BAD_REQUEST
        assert resp_tax.json()["data"]["code"] == "gst.invalid_comparison_input"

        # Negative ITC amount
        resp_itc = client.get(
            "/api/v1/gst/compliance/reconciliation",
            params={
                "business_id": str(business_id),
                "tax_period": "2026-04",
                "gstr3b_itc_amount": "-10.00",
            },
        )
        assert resp_itc.status_code == HTTP_BAD_REQUEST
        assert resp_itc.json()["data"]["code"] == "gst.invalid_comparison_input"

        # Negative component
        resp_comp = client.get(
            "/api/v1/gst/compliance/reconciliation",
            params={
                "business_id": str(business_id),
                "tax_period": "2026-04",
                "gstr3b_cgst_amount": "-1.00",
            },
        )
        assert resp_comp.status_code == HTTP_BAD_REQUEST
        assert resp_comp.json()["data"]["code"] == "gst.invalid_comparison_input"

        # Zero events emitted on rejection
        reconciliation_events = [
            e for e in dispatcher.events
            if isinstance(e, GSTReconciliationCompletedEvent)
        ]
        assert len(reconciliation_events) == 0


def test_reconciliation_rejects_contradictory_component_sums() -> None:
    """API endpoint rejects contradictory component breakdowns with 400 Bad Request."""
    app = create_app(initialize_resources=False)
    business_id, uow, service, dispatcher = build_service_state()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_gst_compliance_unit_of_work] = lambda: uow
    app.dependency_overrides[get_gst_compliance_service] = lambda: service

    with TestClient(app) as client:
        # Outward component sum (90 + 90 = 180) != tax_amount (200)
        resp_outward = client.get(
            "/api/v1/gst/compliance/reconciliation",
            params={
                "business_id": str(business_id),
                "tax_period": "2026-04",
                "gstr3b_tax_amount": "200.00",
                "gstr3b_cgst_amount": "90.00",
                "gstr3b_sgst_amount": "90.00",
            },
        )
        assert resp_outward.status_code == HTTP_BAD_REQUEST
        assert resp_outward.json()["data"]["code"] == "gst.invalid_comparison_input"

        # ITC component sum (50 + 50 = 100) != itc_amount (150)
        resp_itc = client.get(
            "/api/v1/gst/compliance/reconciliation",
            params={
                "business_id": str(business_id),
                "tax_period": "2026-04",
                "gstr3b_itc_amount": "150.00",
                "gstr3b_itc_cgst_amount": "50.00",
                "gstr3b_itc_sgst_amount": "50.00",
            },
        )
        assert resp_itc.status_code == HTTP_BAD_REQUEST
        assert resp_itc.json()["data"]["code"] == "gst.invalid_comparison_input"

        # Zero events emitted on rejection
        reconciliation_events = [
            e for e in dispatcher.events
            if isinstance(e, GSTReconciliationCompletedEvent)
        ]
        assert len(reconciliation_events) == 0


def test_reconciliation_portal_verification_trust_boundary_rejected() -> None:
    """Schema rejects is_portal_verified=True for non-portal sources."""
    business_id, _uow, service, _dispatcher = build_service_state()
    period = service._resolve_period(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )
    summary = GSTAmountSummary()

    # USER_SUPPLIED cannot be portal-verified
    with pytest.raises(ValidationError, match="is_portal_verified cannot be True"):
        GSTRReconciliationReport(
            period=period,
            status=GSTRReconciliationStatus.NOT_COMPARABLE,
            comparison_source=ReconciliationDataSource.USER_SUPPLIED,
            is_portal_verified=True,
            is_comparison_performed=False,
            gstr1_outward=summary,
            itc_books=summary,
            gstr1_total_turnover=Decimal("0.00"),
        )

    # UNPROVIDED cannot be portal-verified
    with pytest.raises(ValidationError, match="is_portal_verified cannot be True"):
        GSTRReconciliationReport(
            period=period,
            status=GSTRReconciliationStatus.NOT_COMPARABLE,
            comparison_source=ReconciliationDataSource.UNPROVIDED,
            is_portal_verified=True,
            is_comparison_performed=False,
            gstr1_outward=summary,
            itc_books=summary,
            gstr1_total_turnover=Decimal("0.00"),
        )

    # GOVERNMENT_PORTAL cannot be claimed without authorized provider evidence
    with pytest.raises(
        ValidationError,
        match="Government portal comparison source cannot be claimed",
    ):
        GSTRReconciliationReport(
            period=period,
            status=GSTRReconciliationStatus.NOT_COMPARABLE,
            comparison_source=ReconciliationDataSource.GOVERNMENT_PORTAL,
            is_portal_verified=False,
            is_comparison_performed=False,
            gstr1_outward=summary,
            itc_books=summary,
            gstr1_total_turnover=Decimal("0.00"),
        )


def test_reconciliation_matched_status_requires_passed_comparison() -> None:
    """Schema rejects status=MATCHED unless both outward and ITC passed."""
    business_id, _uow, service, _dispatcher = build_service_state()
    period = service._resolve_period(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )
    summary = GSTAmountSummary()
    discrepancy = GSTRReconciliationDiscrepancy(
        taxable_value=Decimal("0.00"),
        cgst_amount=Decimal("0.00"),
        sgst_amount=Decimal("0.00"),
        igst_amount=Decimal("0.00"),
        utgst_amount=Decimal("0.00"),
        cess_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("0.00"),
    )

    # Unperformed comparison cannot be MATCHED
    with pytest.raises(
        ValidationError,
        match="status cannot be 'matched' when comparison was not performed",
    ):
        GSTRReconciliationReport(
            period=period,
            status=GSTRReconciliationStatus.MATCHED,
            comparison_source=ReconciliationDataSource.UNPROVIDED,
            is_comparison_performed=False,
            gstr1_outward=summary,
            itc_books=summary,
            gstr1_total_turnover=Decimal("0.00"),
        )

    # Unmatched outward cannot be MATCHED
    with pytest.raises(
        ValidationError,
        match="requires both outward and ITC to be compared and matched",
    ):
        GSTRReconciliationReport(
            period=period,
            status=GSTRReconciliationStatus.MATCHED,
            comparison_source=ReconciliationDataSource.USER_SUPPLIED,
            is_comparison_performed=True,
            is_outward_compared=True,
            is_itc_compared=True,
            is_outward_matched=False,
            is_itc_matched=True,
            gstr1_outward=summary,
            gstr3b_outward=summary,
            outward_discrepancy=discrepancy,
            itc_books=summary,
            itc_gstr3b=summary,
            itc_discrepancy=discrepancy,
            gstr1_total_turnover=Decimal("0.00"),
            gstr3b_total_turnover=Decimal("0.00"),
            turnover_discrepancy=Decimal("0.00"),
        )


def test_reconciliation_nullability_and_lifecycle_invariants() -> None:
    """Schema enforces null fields when uncompared and non-null when compared."""
    business_id, _uow, service, _dispatcher = build_service_state()
    period = service._resolve_period(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )
    summary = GSTAmountSummary()
    discrepancy = GSTRReconciliationDiscrepancy()

    # Outward not compared but discrepancy provided
    with pytest.raises(
        ValidationError,
        match="Outward comparison fields must be None",
    ):
        GSTRReconciliationReport(
            period=period,
            status=GSTRReconciliationStatus.NOT_COMPARABLE,
            comparison_source=ReconciliationDataSource.USER_SUPPLIED,
            is_comparison_performed=True,
            is_outward_compared=False,
            outward_discrepancy=discrepancy,
            gstr1_outward=summary,
            itc_books=summary,
            gstr1_total_turnover=Decimal("0.00"),
        )

    # ITC not compared but itc_discrepancy provided
    with pytest.raises(
        ValidationError,
        match="ITC comparison fields must be None",
    ):
        GSTRReconciliationReport(
            period=period,
            status=GSTRReconciliationStatus.NOT_COMPARABLE,
            comparison_source=ReconciliationDataSource.USER_SUPPLIED,
            is_comparison_performed=True,
            is_itc_compared=False,
            itc_discrepancy=discrepancy,
            gstr1_outward=summary,
            itc_books=summary,
            gstr1_total_turnover=Decimal("0.00"),
        )


def test_reconciliation_event_trust_boundary_and_match_invariants() -> None:
    """Event enforces fail-closed defaults and trust boundary."""
    business_id = uuid.uuid4()

    # Default construction is fail-closed
    ev_default = GSTReconciliationCompletedEvent(
        business_id=business_id,
        tax_period="2026-04",
        status="not_comparable",
    )
    assert ev_default.is_comparison_performed is False
    assert ev_default.is_matched is False
    assert ev_default.comparison_source == "unprovided"
    assert ev_default.is_portal_verified is False

    # is_portal_verified=True on non-portal source raises ValueError
    with pytest.raises(ValueError, match="is_portal_verified cannot be True"):
        GSTReconciliationCompletedEvent(
            business_id=business_id,
            tax_period="2026-04",
            status="not_comparable",
            comparison_source="user_supplied",
            is_portal_verified=True,
        )

    # government_portal cannot be claimed without authorized provider evidence
    with pytest.raises(
        ValueError,
        match="government portal provenance cannot be claimed",
    ):
        GSTReconciliationCompletedEvent(
            business_id=business_id,
            tax_period="2026-04",
            status="not_comparable",
            comparison_source="government_portal",
        )

    # is_matched=True when is_comparison_performed=False raises ValueError
    with pytest.raises(ValueError, match="is_matched cannot be True"):
        GSTReconciliationCompletedEvent(
            business_id=business_id,
            tax_period="2026-04",
            status="not_comparable",
            is_comparison_performed=False,
            is_matched=True,
        )

    # is_matched=True when status != "matched" raises ValueError
    with pytest.raises(ValueError, match="is_matched cannot be True"):
        GSTReconciliationCompletedEvent(
            business_id=business_id,
            tax_period="2026-04",
            status="discrepancy_detected",
            is_comparison_performed=True,
            is_matched=True,
        )

    # is_matched=False when status == "matched" raises ValueError
    with pytest.raises(ValueError, match="contradicts is_matched"):
        GSTReconciliationCompletedEvent(
            business_id=business_id,
            tax_period="2026-04",
            status="matched",
            is_comparison_performed=True,
            is_matched=False,
        )

    # unsupported comparison_source raises ValueError
    with pytest.raises(ValueError, match="unsupported comparison_source"):
        GSTReconciliationCompletedEvent(
            business_id=business_id,
            tax_period="2026-04",
            status="not_comparable",
            comparison_source="mock",
        )


def test_reconciliation_csv_export_uncompared_null_representation() -> None:
    """CSV export flattens None fields into empty string cells rather than '0.00'."""
    business_id, _uow, service, _dispatcher = build_service_state()
    period = service._resolve_period(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )
    gstr1_outward = GSTAmountSummary(
        taxable_value=Decimal("5000.00"),
        cgst_amount=Decimal("450.00"),
        sgst_amount=Decimal("450.00"),
        tax_amount=Decimal("900.00"),
        total_amount=Decimal("5900.00"),
    )
    itc_books = GSTAmountSummary(
        taxable_value=Decimal("2000.00"),
        cgst_amount=Decimal("180.00"),
        sgst_amount=Decimal("180.00"),
        tax_amount=Decimal("360.00"),
        total_amount=Decimal("2360.00"),
    )

    report = service._build_non_comparable_report(
        period=period,
        gstr1_outward=gstr1_outward,
        itc_books=itc_books,
        gstr1_total_turnover=Decimal("5000.00"),
    )

    csv_data = service.export_csv(report)
    assert "outward_discrepancy.tax_amount" in csv_data
    assert "itc_discrepancy.tax_amount" in csv_data

    # Parse CSV to inspect cells
    reader = py_csv.DictReader(io.StringIO(csv_data))
    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]

    # Verify uncompared discrepancy cells are empty string "", NOT "0.00" or "None"
    assert row["outward_discrepancy.tax_amount"] == ""
    assert row["outward_discrepancy.cgst_amount"] == ""
    assert row["itc_discrepancy.tax_amount"] == ""
    assert row["turnover_discrepancy"] == ""
    assert row["gstr3b_total_turnover"] == ""
    assert row["status"] == "not_comparable"
    assert row["is_comparison_performed"] == "False"


def test_reconciliation_api_rejects_client_claiming_portal_verification() -> None:
    """API endpoint rejects client assertions of portal verification or source."""
    app = create_app(initialize_resources=False)
    business_id, uow, service, dispatcher = build_service_state()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_gst_compliance_unit_of_work] = lambda: uow
    app.dependency_overrides[get_gst_compliance_service] = lambda: service

    with TestClient(app) as client:
        # 1. Reject is_portal_verified=true
        resp_verified = client.get(
            "/api/v1/gst/compliance/reconciliation",
            params={
                "business_id": str(business_id),
                "tax_period": "2026-04",
                "is_portal_verified": "true",
            },
        )
        assert resp_verified.status_code == HTTP_BAD_REQUEST
        assert resp_verified.json()["data"]["code"] == "gst.invalid_comparison_input"

        # 2. Reject comparison_source=government_portal
        resp_portal = client.get(
            "/api/v1/gst/compliance/reconciliation",
            params={
                "business_id": str(business_id),
                "tax_period": "2026-04",
                "comparison_source": "government_portal",
            },
        )
        assert resp_portal.status_code == HTTP_BAD_REQUEST
        assert resp_portal.json()["data"]["code"] == "gst.invalid_comparison_input"

        # Zero events emitted on rejection
        reconciliation_events = [
            e
            for e in dispatcher.events
            if isinstance(e, GSTReconciliationCompletedEvent)
        ]
        assert len(reconciliation_events) == 0


@pytest.mark.asyncio
async def test_reconciliation_direct_service_rejects_unauthorized_provenance() -> None:
    """Service directly rejects portal verification claims without provider evidence."""
    business_id, _uow, service, dispatcher = build_service_state()

    # 1. Reject is_portal_verified=True
    with pytest.raises(GSTComparisonInputValidationException) as exc_verified:
        await service.generate_reconciliation(
            GSTReportRequest(business_id=business_id, tax_period="2026-04"),
            is_portal_verified=True,
        )
    assert exc_verified.value.error_code == "gst.invalid_comparison_input"

    # 2. Reject comparison_source=GOVERNMENT_PORTAL enum
    with pytest.raises(GSTComparisonInputValidationException) as exc_source_enum:
        await service.generate_reconciliation(
            GSTReportRequest(business_id=business_id, tax_period="2026-04"),
            comparison_source=ReconciliationDataSource.GOVERNMENT_PORTAL,
        )
    assert exc_source_enum.value.error_code == "gst.invalid_comparison_input"

    # 3. Reject comparison_source="government_portal" string
    with pytest.raises(GSTComparisonInputValidationException) as exc_source_str:
        await service.generate_reconciliation(
            GSTReportRequest(business_id=business_id, tax_period="2026-04"),
            comparison_source="government_portal",
        )
    assert exc_source_str.value.error_code == "gst.invalid_comparison_input"

    # Zero events emitted
    assert len(dispatcher.events) == 0


@pytest.mark.asyncio
async def test_reconciliation_event_derived_strictly_from_report() -> None:
    """Event factory derives event strictly from report with invariant parity."""
    business_id, _uow, service, _dispatcher = build_service_state()

    # 1. Non-comparable report derivation
    report_uncomp = await service.generate_reconciliation(
        GSTReportRequest(business_id=business_id, tax_period="2026-04"),
    )
    ev_uncomp = GSTReconciliationCompletedEvent.from_report(report_uncomp)
    assert ev_uncomp.business_id == report_uncomp.period.business_id
    assert ev_uncomp.tax_period == report_uncomp.period.tax_period
    assert ev_uncomp.status == report_uncomp.status.value
    assert ev_uncomp.is_comparison_performed is report_uncomp.is_comparison_performed
    assert ev_uncomp.is_matched is False
    assert ev_uncomp.comparison_source == report_uncomp.comparison_source.value
    assert ev_uncomp.is_portal_verified is report_uncomp.is_portal_verified

    # 2. Matched report derivation
    gstr3b_liability = GSTAmountSummary(
        taxable_value=Decimal("1000.00"),
        cgst_amount=Decimal("90.00"),
        sgst_amount=Decimal("90.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
    )
    gstr3b_itc = GSTAmountSummary(
        taxable_value=Decimal("600.00"),
        cgst_amount=Decimal("54.00"),
        sgst_amount=Decimal("54.00"),
        tax_amount=Decimal("108.00"),
        total_amount=Decimal("708.00"),
    )
    report_matched = await service.generate_reconciliation(
        GSTReportRequest(business_id=business_id, tax_period="2026-04"),
        gstr3b_liability_override=gstr3b_liability,
        gstr3b_itc_override=gstr3b_itc,
    )
    ev_matched = GSTReconciliationCompletedEvent.from_report(report_matched)
    assert ev_matched.status == "matched"
    assert ev_matched.is_comparison_performed is True
    assert ev_matched.is_matched is True
    assert ev_matched.comparison_source == "user_supplied"
    assert ev_matched.is_portal_verified is False


@pytest.mark.asyncio
async def test_reconciliation_allowlist_evolution_and_mock_defense(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Allowlist evolution and testbed sources cannot authorize caller overrides."""
    business_id, _uow, service, dispatcher = build_service_state()
    override = GSTAmountSummary(
        taxable_value=Decimal("1000.00"),
        cgst_amount=Decimal("90.00"),
        sgst_amount=Decimal("90.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
    )

    # 1. Testbed sources (e.g. SANDBOX_GST_VERIFIER, mock, sandbox) are rejected
    for testbed_src in (
        "SANDBOX_GST_VERIFIER",
        "sandbox_gst_verifier",
        "mock",
        "sandbox",
        "testbed",
    ):
        with pytest.raises(GSTComparisonInputValidationException) as exc_mock:
            await service.generate_reconciliation(
                GSTReportRequest(business_id=business_id, tax_period="2026-04"),
                gstr3b_liability_override=override,
                comparison_source=testbed_src,
            )
        assert exc_mock.value.error_code == "gst.invalid_comparison_input"

    # 2. Arbitrary unsupported sources are rejected
    with pytest.raises(GSTComparisonInputValidationException) as exc_unsupp:
        await service.generate_reconciliation(
            GSTReportRequest(business_id=business_id, tax_period="2026-04"),
            gstr3b_liability_override=override,
            comparison_source="arbitrary_external_provider",
        )
    assert exc_unsupp.value.error_code == "gst.invalid_comparison_input"

    # 3. Future allowlist evolution defense:
    # Even if AUTHORIZED_PRODUCTION_VERIFICATION_SOURCES is extended in the future,
    # caller-supplied overrides can NEVER claim authorized provider provenance.
    monkeypatch.setattr(
        comp_svc_mod,
        "AUTHORIZED_PRODUCTION_VERIFICATION_SOURCES",
        frozenset({"FUTURE_PORTAL_GSP"}),
    )
    with pytest.raises(GSTComparisonInputValidationException) as exc_future:
        await service.generate_reconciliation(
            GSTReportRequest(business_id=business_id, tax_period="2026-04"),
            gstr3b_liability_override=override,
            comparison_source="FUTURE_PORTAL_GSP",
        )
    assert exc_future.value.error_code == "gst.invalid_comparison_input"

    # Zero events dispatched on all rejections
    assert len(dispatcher.events) == 0


@pytest.mark.asyncio
async def test_reconciliation_user_data_cannot_become_verified_via_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Environment changes cannot promote user-supplied data to portal-verified."""
    business_id, _uow, service, _dispatcher = build_service_state()
    override = GSTAmountSummary(
        taxable_value=Decimal("1000.00"),
        cgst_amount=Decimal("90.00"),
        sgst_amount=Decimal("90.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
    )

    for env_name in ("testing", "development", "staging", "production"):
        monkeypatch.setenv("TAX_PILOT_ENVIRONMENT", env_name)
        monkeypatch.setenv("ENVIRONMENT", env_name)

        # Standard reconciliation with overrides remains user_supplied and unverified
        report = await service.generate_reconciliation(
            GSTReportRequest(business_id=business_id, tax_period="2026-04"),
            gstr3b_liability_override=override,
            gstr3b_itc_override=override,
        )
        assert report.comparison_source == ReconciliationDataSource.USER_SUPPLIED
        assert report.is_portal_verified is False

        # Explicit assertion of portal verification is strictly rejected
        with pytest.raises(GSTComparisonInputValidationException):
            await service.generate_reconciliation(
                GSTReportRequest(business_id=business_id, tax_period="2026-04"),
                gstr3b_liability_override=override,
                is_portal_verified=True,
            )


def test_reconciliation_api_rejects_mock_and_unsupported_sources() -> None:
    """API endpoint rejects mock/sandbox and arbitrary comparison sources."""
    app = create_app(initialize_resources=False)
    business_id, uow, service, dispatcher = build_service_state()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_gst_compliance_unit_of_work] = lambda: uow
    app.dependency_overrides[get_gst_compliance_service] = lambda: service

    with TestClient(app) as client:
        for bad_source in (
            "mock",
            "sandbox",
            "SANDBOX_GST_VERIFIER",
            "external",
            "foo",
        ):
            resp = client.get(
                "/api/v1/gst/compliance/reconciliation",
                params={
                    "business_id": str(business_id),
                    "tax_period": "2026-04",
                    "comparison_source": bad_source,
                },
            )
            assert resp.status_code == HTTP_BAD_REQUEST
            assert resp.json()["data"]["code"] == "gst.invalid_comparison_input"

        assert len(dispatcher.events) == 0


def test_reconciliation_report_and_event_cross_layer_invariants() -> None:
    """Schema and event enforce statutory claim and non-comparable risk invariants."""
    business_id, _uow, service, _dispatcher = build_service_state()
    period = service._resolve_period(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )
    summary = GSTAmountSummary()

    # 1. statutory_determination_claim must be False
    with pytest.raises(
        ValidationError,
        match="statutory_determination_claim must always be False",
    ):
        GSTRReconciliationReport(
            period=period,
            status=GSTRReconciliationStatus.NOT_COMPARABLE,
            statutory_determination_claim=True,
            gstr1_outward=summary,
            itc_books=summary,
            gstr1_total_turnover=Decimal("0.00"),
        )

    # 2. NOT_COMPARABLE cannot have drc01b_risk=True
    with pytest.raises(
        ValidationError,
        match="status cannot be 'not_comparable' when drc01b_risk",
    ):
        GSTRReconciliationReport(
            period=period,
            status=GSTRReconciliationStatus.NOT_COMPARABLE,
            drc01b_risk=True,
            gstr1_outward=summary,
            itc_books=summary,
            gstr1_total_turnover=Decimal("0.00"),
        )

    # 3. NOT_COMPARABLE cannot have drc01c_risk=True
    with pytest.raises(
        ValidationError,
        match="status cannot be 'not_comparable' when drc01b_risk",
    ):
        GSTRReconciliationReport(
            period=period,
            status=GSTRReconciliationStatus.NOT_COMPARABLE,
            drc01c_risk=True,
            gstr1_outward=summary,
            itc_books=summary,
            gstr1_total_turnover=Decimal("0.00"),
        )


@pytest.mark.asyncio
async def test_reconciliation_unknown_vs_zero_json_and_csv_serialization() -> None:
    """Verify separation between unknown (null / empty) and genuine zero values."""
    business_id, _uow, service, _dispatcher = build_service_state()

    # 1. Non-comparable report: uncompared fields are None (null) and "" in CSV
    report_uncomp = await service.generate_reconciliation(
        GSTReportRequest(business_id=business_id, tax_period="2026-04"),
    )
    assert report_uncomp.outward_discrepancy is None
    assert report_uncomp.itc_discrepancy is None
    assert report_uncomp.turnover_discrepancy is None
    assert report_uncomp.gstr3b_total_turnover is None

    csv_uncomp = service.export_csv(report_uncomp)
    reader_uncomp = py_csv.DictReader(io.StringIO(csv_uncomp))
    row_uncomp = list(reader_uncomp)[0]
    assert row_uncomp["outward_discrepancy.tax_amount"] == ""
    assert row_uncomp["itc_discrepancy.tax_amount"] == ""
    assert row_uncomp["turnover_discrepancy"] == ""
    assert row_uncomp["gstr3b_total_turnover"] == ""

    # 2. Matched report: discrepancy fields are Decimal("0.00") and "0.00" in CSV
    matching_summary = GSTAmountSummary(
        taxable_value=Decimal("1000.00"),
        cgst_amount=Decimal("90.00"),
        sgst_amount=Decimal("90.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
    )
    itc_summary = GSTAmountSummary(
        taxable_value=Decimal("600.00"),
        cgst_amount=Decimal("54.00"),
        sgst_amount=Decimal("54.00"),
        tax_amount=Decimal("108.00"),
        total_amount=Decimal("708.00"),
    )
    report_matched = await service.generate_reconciliation(
        GSTReportRequest(business_id=business_id, tax_period="2026-04"),
        gstr3b_liability_override=matching_summary,
        gstr3b_itc_override=itc_summary,
    )
    assert report_matched.outward_discrepancy is not None
    assert report_matched.outward_discrepancy.tax_amount == Decimal("0.00")
    assert report_matched.turnover_discrepancy == Decimal("0.00")

    csv_matched = service.export_csv(report_matched)
    reader_matched = py_csv.DictReader(io.StringIO(csv_matched))
    row_matched = list(reader_matched)[0]
    assert row_matched["outward_discrepancy.tax_amount"] == "0.00"
    assert row_matched["turnover_discrepancy"] == "0.00"
    assert row_matched["status"] == "matched"




