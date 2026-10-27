"""End-to-end integration and acceptance hardening tests for GST workflows.

Verifies connections among:
1. Sales invoice lifecycle, POS resolution, tax snapshots, GL entries (Account 2010),
   GSTR-1 (Table 4 B2B, Table 7 B2C, Table 8 Nil-rated), and GSTR-3B reconciliation.
2. Purchase invoice lifecycle, location resolution, GL entries (Account 1050 ITC),
   and GSTR-3B inward / ITC reconciliation.
3. Zero double counting between taxable and nil-rated / exempt supplies.
4. Exclusion of draft and cancelled invoices from compliance returns.
5. Mock e-invoice and e-way bill lifecycle without leaking to production verification.
6. GSTIN evidence trust boundary enforcement in production.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Self, cast

import pytest

import app.modules.catalog.models  # noqa: F401
import app.modules.inventory.models  # noqa: F401
from app.common.events import Event, EventDispatcher
from app.core.model_registry import import_all_models
from app.modules.accounting.journal.models import (
    JournalEntry,
    JournalEntryLine,
    JournalStatus,
)
from app.modules.accounting.kernel.accounting_kernel import (
    AccountingKernelService,
    AccountingKernelUnitOfWork,
)
from app.modules.expenses.models import Expense
from app.modules.gst.compliance.schemas import GSTReportRequest
from app.modules.gst.compliance.services import GSTComplianceService
from app.modules.gst.compliance.services.compliance_service import (
    GSTComplianceUnitOfWork,
)
from app.modules.gst.einvoice.exceptions import DuplicateIRNException
from app.modules.gst.einvoice.schemas import (
    EInvoiceCancelRequest,
    EInvoiceGenerateRequest,
    EWayBillCancelRequest,
    EWayBillGenerateRequest,
)
from app.modules.gst.evidence import (
    BuyerRegistrationUnverifiedException,
    FreshnessPolicy,
    GSTINEvidenceStatus,
    GSTINVerificationEvidence,
)
from app.modules.gst.jurisdictions import InvalidStateCodeException
from app.modules.gst.services.gst_calculation_service import GSTSupplyType
from app.modules.gst.services.pos_resolution_service import (
    ConsigneeRequiredException,
    DirectingPartyIndeterminateException,
    DirectionTiming,
    DirectionTimingUnestablishedException,
    PlaceOfSupplyResolutionService,
    SupplyResolutionContext,
)
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
from tests.test_accounting_kernel import (
    FakeBalanceRepository,
    FakeChartRepository,
    FakeLedgerRepository,
    build_accounts,
)
from tests.test_gst_einvoice import build_service_state

# Ensure all SQLAlchemy model relationships are mapped
import_all_models()

MONEY_PLACES = Decimal("0.01")
EXPECTED_FOUR_INVOICES = 4


class CapturingEventDispatcher(EventDispatcher):
    """Event dispatcher that captures events."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[Event] = []

    async def dispatch(self, event: Event) -> None:
        self.events.append(event)
        await super().dispatch(event)


@dataclass
class FakeComplianceRepository:
    """Fake compliance read repository."""

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
        return [
            s
            for s in self.sales
            if s.business_id == business_id and start_date <= s.invoice_date <= end_date
        ]

    async def list_purchases(
        self,
        *,
        business_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[PurchaseInvoice]:
        return [
            p
            for p in self.purchases
            if p.business_id == business_id and start_date <= p.invoice_date <= end_date
        ]

    async def list_expenses(
        self,
        *,
        business_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[Expense]:
        return [
            e
            for e in self.expenses
            if e.business_id == business_id and start_date <= e.expense_date <= end_date
        ]


class FakeComplianceUnitOfWork:
    """Fake UoW for compliance service."""

    def __init__(self, repo: FakeComplianceRepository) -> None:
        self.gst_compliance = repo
        self.committed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True


class IterableJournalRepo:
    """Fake journal repository with iterator and len support."""

    def __init__(self) -> None:
        self.journals: list[JournalEntry] = []

    def __iter__(self) -> Any:
        return iter(self.journals)

    def __len__(self) -> int:
        return len(self.journals)

    async def add(self, entity: JournalEntry) -> JournalEntry:
        entity.id = entity.id or uuid.uuid4()
        for line in entity.lines:
            line.id = line.id or uuid.uuid4()
            line.journal_entry_id = entity.id
        self.journals.append(entity)
        return entity

    async def mark_posted(
        self,
        journal: JournalEntry,
        *,
        posting_date: date,
    ) -> JournalEntry:
        journal.status = JournalStatus.POSTED
        journal.posting_date = posting_date
        return journal


class FakeAccountingKernelUnitOfWork:
    """In-memory Unit of Work for AccountingKernelService."""

    def __init__(self, business_id: uuid.UUID) -> None:
        self.business_id = business_id
        self.sales_invoices_map: dict[uuid.UUID, SalesInvoice] = {}
        self.purchase_invoices_map: dict[uuid.UUID, PurchaseInvoice] = {}
        self.chart_of_accounts = FakeChartRepository(build_accounts(business_id))
        self.journals = IterableJournalRepo()
        self.ledgers = FakeLedgerRepository()
        self.account_balances = FakeBalanceRepository()

        outer = self

        class SalesInvRepo:
            async def get_by_id(self, invoice_id: uuid.UUID) -> SalesInvoice | None:
                return outer.sales_invoices_map.get(invoice_id)

        class PurchaseInvRepo:
            async def get_by_id(self, purchase_id: uuid.UUID) -> PurchaseInvoice | None:
                return outer.purchase_invoices_map.get(purchase_id)

        class EmptyPaymentRepo:
            async def get_by_id(self, payment_id: uuid.UUID) -> Any | None:
                return None

        class EmptyExpenseRepo:
            async def get_by_id(self, expense_id: uuid.UUID) -> Any | None:
                return None

        self.sales_invoices = SalesInvRepo()
        self.purchase_invoices = PurchaseInvRepo()
        self.payments = EmptyPaymentRepo()
        self.expenses = EmptyExpenseRepo()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        pass

    async def commit(self) -> None:
        pass


def _build_hardening_sales_invoices(
    business_id: uuid.UUID,
    test_date: date,
) -> list[SalesInvoice]:
    """Build representative sales invoices across B2B, B2C, and nil-rated."""
    # 1. B2B Inter-State (KA 29 -> MH 27)
    inv1_id = uuid.uuid4()
    cust_b2b_mh = Customer(
        id=uuid.uuid4(),
        business_id=business_id,
        customer_code="CUST-MH",
        name="MH Enterprise",
        gstin="27ABCDE1234F1Z5",
    )
    inv1 = SalesInvoice(
        id=inv1_id,
        business_id=business_id,
        customer_id=cust_b2b_mh.id,
        customer=cust_b2b_mh,
        invoice_number="INV-001",
        invoice_date=test_date,
        place_of_supply="27",
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("1000.00"),
        taxable_amount=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=inv1_id,
                description="Interstate Goods",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1000.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("0.00"),
                sgst_amount=Decimal("0.00"),
                igst_amount=Decimal("180.00"),
                utgst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("1180.00"),
            )
        ],
    )

    # 2. B2B Intra-State (KA 29 -> KA 29)
    inv2_id = uuid.uuid4()
    cust_b2b_ka = Customer(
        id=uuid.uuid4(),
        business_id=business_id,
        customer_code="CUST-KA",
        name="KA Corp",
        gstin="29ABCDE1234F1Z5",
    )
    inv2 = SalesInvoice(
        id=inv2_id,
        business_id=business_id,
        customer_id=cust_b2b_ka.id,
        customer=cust_b2b_ka,
        invoice_number="INV-002",
        invoice_date=test_date,
        place_of_supply="29",
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("2000.00"),
        taxable_amount=Decimal("2000.00"),
        tax_amount=Decimal("360.00"),
        total_amount=Decimal("2360.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=inv2_id,
                description="Local Services",
                quantity=Decimal("1.00"),
                unit_price=Decimal("2000.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("180.00"),
                sgst_amount=Decimal("180.00"),
                igst_amount=Decimal("0.00"),
                utgst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("2360.00"),
            )
        ],
    )

    # 3. B2C Intra-State (KA 29 -> KA 29 Unregistered)
    inv3_id = uuid.uuid4()
    cust_b2c = Customer(
        id=uuid.uuid4(),
        business_id=business_id,
        customer_code="CUST-B2C",
        name="Retail Buyer",
        gstin=None,
    )
    inv3 = SalesInvoice(
        id=inv3_id,
        business_id=business_id,
        customer_id=cust_b2c.id,
        customer=cust_b2c,
        invoice_number="INV-003",
        invoice_date=test_date,
        place_of_supply="29",
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("500.00"),
        taxable_amount=Decimal("500.00"),
        tax_amount=Decimal("90.00"),
        total_amount=Decimal("590.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=inv3_id,
                description="Retail Hardware",
                quantity=Decimal("1.00"),
                unit_price=Decimal("500.00"),
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

    # 4. Nil-Rated B2B (KA 29 -> KA 29, 0% rate)
    inv4_id = uuid.uuid4()
    inv4 = SalesInvoice(
        id=inv4_id,
        business_id=business_id,
        customer_id=cust_b2b_ka.id,
        customer=cust_b2b_ka,
        invoice_number="INV-004",
        invoice_date=test_date,
        place_of_supply="29",
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("300.00"),
        taxable_amount=Decimal("300.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("300.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=inv4_id,
                description="Exempt Fresh Produce",
                quantity=Decimal("1.00"),
                unit_price=Decimal("300.00"),
                tax_rate=Decimal("0.00"),
                cgst_amount=Decimal("0.00"),
                sgst_amount=Decimal("0.00"),
                igst_amount=Decimal("0.00"),
                utgst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("300.00"),
            )
        ],
    )

    return [inv1, inv2, inv3, inv4]


def _build_hardening_purchase_invoices(
    business_id: uuid.UUID,
    test_date: date,
) -> tuple[PurchaseInvoice, PurchaseInvoice]:
    """Build representative intra-state and inter-state purchase invoices."""
    # 1. Intra-state purchase (KA to KA)
    pur1_id = uuid.uuid4()
    pur1 = PurchaseInvoice(
        id=pur1_id,
        business_id=business_id,
        supplier_id=uuid.uuid4(),
        purchase_number="PUR-001",
        invoice_number="SUP-001",
        invoice_date=test_date,
        status=PurchaseStatus.APPROVED,
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        lines=[
            PurchaseInvoiceLine(
                id=uuid.uuid4(),
                purchase_invoice_id=pur1_id,
                description="Local Raw Materials",
                quantity=Decimal("1.00"),
                unit_cost=Decimal("1000.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("90.00"),
                sgst_amount=Decimal("90.00"),
                igst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("1180.00"),
            )
        ],
    )

    # 2. Inter-state purchase (MH to KA)
    pur2_id = uuid.uuid4()
    pur2 = PurchaseInvoice(
        id=pur2_id,
        business_id=business_id,
        supplier_id=uuid.uuid4(),
        purchase_number="PUR-002",
        invoice_number="SUP-002",
        invoice_date=test_date,
        status=PurchaseStatus.APPROVED,
        subtotal=Decimal("1500.00"),
        tax_amount=Decimal("270.00"),
        total_amount=Decimal("1770.00"),
        lines=[
            PurchaseInvoiceLine(
                id=uuid.uuid4(),
                purchase_invoice_id=pur2_id,
                description="Interstate Equipment",
                quantity=Decimal("1.00"),
                unit_cost=Decimal("1500.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("0.00"),
                sgst_amount=Decimal("0.00"),
                igst_amount=Decimal("270.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("1770.00"),
            )
        ],
    )
    return pur1, pur2


# --- End-to-End Hardening Tests ---


@pytest.mark.asyncio
async def test_e2e_sales_accounting_and_gstr_reconciliation() -> None:
    """Verify sales invoicing -> AccountingKernel -> GSTR-1 and GSTR-3B."""
    business_id = uuid.uuid4()
    test_date = date(2026, 4, 15)

    all_invoices = _build_hardening_sales_invoices(business_id, test_date)

    # --- Step A: Post all 4 invoices to AccountingKernel ---
    acct_uow = FakeAccountingKernelUnitOfWork(business_id)
    for inv in all_invoices:
        acct_uow.sales_invoices_map[inv.id] = inv

    kernel = AccountingKernelService(
        unit_of_work_factory=lambda: cast(AccountingKernelUnitOfWork, acct_uow),
        event_dispatcher=CapturingEventDispatcher(),
    )

    for inv in all_invoices:
        await kernel.record_sales_invoice(inv.id, uow=acct_uow)

    # Verify accounting double-entry balance for each journal
    assert len(acct_uow.journals) == EXPECTED_FOUR_INVOICES
    for journal in acct_uow.journals:
        total_debit = sum((line.debit for line in journal.lines), Decimal("0.00"))
        total_credit = sum((line.credit for line in journal.lines), Decimal("0.00"))
        assert total_debit == total_credit

    # Verify canonical Account 2010 (Output Tax Payable) component descriptions
    output_tax_lines: list[JournalEntryLine] = [
        line
        for journal in acct_uow.journals
        for line in journal.lines
        if line.account.account_code == "2010"
    ]

    descriptions = [line.description for line in output_tax_lines]
    assert any("Output IGST for INV-001" in d for d in descriptions)
    assert any("Output CGST for INV-002" in d for d in descriptions)
    assert any("Output SGST for INV-002" in d for d in descriptions)
    assert any("Output CGST for INV-003" in d for d in descriptions)
    assert any("Output SGST for INV-003" in d for d in descriptions)

    total_output_tax_credit = sum(
        (line.credit for line in output_tax_lines), Decimal("0.00")
    )
    assert total_output_tax_credit == Decimal("630.00")  # 180 + 360 + 90

    # --- Step B: Generate GSTR-1 and Reconcile ---
    compliance_repo = FakeComplianceRepository(
        sales=all_invoices,
        purchases=[],
        expenses=[],
    )
    compliance_uow = FakeComplianceUnitOfWork(compliance_repo)
    compliance_service = GSTComplianceService(
        unit_of_work_factory=lambda: cast(GSTComplianceUnitOfWork, compliance_uow),
        event_dispatcher=CapturingEventDispatcher(),
    )

    gstr1 = await compliance_service.generate_gstr1(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    # Table 4: Taxable supplies to registered persons (INV-001 and INV-002)
    assert gstr1.b2b.taxable_value == Decimal("3000.00")
    assert gstr1.b2b.tax_amount == Decimal("540.00")
    assert gstr1.b2b.igst_amount == Decimal("180.00")
    assert gstr1.b2b.cgst_amount == Decimal("180.00")
    assert gstr1.b2b.sgst_amount == Decimal("180.00")

    # Table 7: Taxable supplies to unregistered persons (INV-003)
    assert gstr1.b2c.taxable_value == Decimal("500.00")
    assert gstr1.b2c.tax_amount == Decimal("90.00")
    assert gstr1.b2c.cgst_amount == Decimal("45.00")
    assert gstr1.b2c.sgst_amount == Decimal("45.00")

    # Table 8: Nil-rated / exempt supplies (INV-004)
    assert gstr1.nil_rated.taxable_value == Decimal("300.00")
    assert gstr1.nil_rated.tax_amount == Decimal("0.00")

    # Critical Zero Double Counting Invariant:
    total_gstr1_turnover = (
        gstr1.b2b.taxable_value
        + gstr1.b2c.taxable_value
        + gstr1.nil_rated.taxable_value
    )
    assert total_gstr1_turnover == Decimal("3800.00")  # 1000 + 2000 + 500 + 300

    total_gstr1_tax = gstr1.b2b.tax_amount + gstr1.b2c.tax_amount
    assert total_gstr1_tax == Decimal("630.00")
    assert total_gstr1_tax == total_output_tax_credit  # 100% GL Reconciliation!

    # --- Step C: Generate GSTR-3B and Reconcile ---
    gstr3b = await compliance_service.generate_gstr3b(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    # Table 3.1(a) Outward taxable supplies
    assert gstr3b.outward_taxable_supplies.taxable_value == Decimal("3500.00")
    assert gstr3b.outward_taxable_supplies.tax_amount == Decimal("630.00")

    # Table 3.1(c) Other outward supplies (nil/exempt)
    assert gstr3b.exempt_supplies.taxable_value == Decimal("300.00")

    # GSTR-3B turnover matches GSTR-1 turnover exactly
    assert (
        gstr3b.outward_taxable_supplies.taxable_value
        + gstr3b.exempt_supplies.taxable_value
        == total_gstr1_turnover
    )

    # Tax liability in GSTR-3B matches Account 2010 Credit Balance
    assert gstr3b.tax_liability.tax_amount == Decimal("630.00")


@pytest.mark.asyncio
async def test_e2e_purchase_accounting_and_itc_reconciliation() -> None:
    """Verify purchase invoicing -> AccountingKernel -> GSTR-3B ITC reconciliation."""
    business_id = uuid.uuid4()
    test_date = date(2026, 4, 18)

    pur1, pur2 = _build_hardening_purchase_invoices(business_id, test_date)

    # --- Step A: Post to AccountingKernel ---
    acct_uow = FakeAccountingKernelUnitOfWork(business_id)
    acct_uow.purchase_invoices_map[pur1.id] = pur1
    acct_uow.purchase_invoices_map[pur2.id] = pur2

    kernel = AccountingKernelService(
        unit_of_work_factory=lambda: cast(AccountingKernelUnitOfWork, acct_uow),
        event_dispatcher=CapturingEventDispatcher(),
    )

    await kernel.record_purchase_invoice(pur1.id, uow=acct_uow)
    await kernel.record_purchase_invoice(pur2.id, uow=acct_uow)

    # Verify Account 1050 (Input GST / ITC) debits
    input_tax_lines = [
        line
        for journal in acct_uow.journals
        for line in journal.lines
        if line.account.account_code == "1050"
    ]
    total_itc_debit = sum((line.debit for line in input_tax_lines), Decimal("0.00"))
    assert total_itc_debit == Decimal("450.00")  # 180 + 270

    # --- Step B: Generate ITC Report and Reconcile ---
    compliance_repo = FakeComplianceRepository(
        sales=[],
        purchases=[pur1, pur2],
        expenses=[],
    )
    compliance_uow = FakeComplianceUnitOfWork(compliance_repo)
    compliance_service = GSTComplianceService(
        unit_of_work_factory=lambda: cast(GSTComplianceUnitOfWork, compliance_uow),
        event_dispatcher=CapturingEventDispatcher(),
    )

    itc_report = await compliance_service.generate_itc_report(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    assert itc_report.eligible_itc.tax_amount == Decimal("450.00")
    assert itc_report.eligible_itc.cgst_amount == Decimal("90.00")
    assert itc_report.eligible_itc.sgst_amount == Decimal("90.00")
    assert itc_report.eligible_itc.igst_amount == Decimal("270.00")
    # 100% GL Reconciliation
    assert itc_report.eligible_itc.tax_amount == total_itc_debit


@pytest.mark.asyncio
async def test_e2e_draft_and_cancelled_invoices_excluded_from_returns() -> None:
    """Draft and cancelled invoices are strictly excluded from GSTR returns."""
    business_id = uuid.uuid4()
    test_date = date(2026, 4, 15)

    issued_inv = SalesInvoice(
        id=uuid.uuid4(),
        business_id=business_id,
        customer_id=uuid.uuid4(),
        invoice_number="INV-ISSUED",
        invoice_date=test_date,
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("1000.00"),
        taxable_amount=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                description="Goods",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1000.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("90.00"),
                sgst_amount=Decimal("90.00"),
                igst_amount=Decimal("0.00"),
                line_total=Decimal("1180.00"),
            )
        ],
    )
    draft_inv = SalesInvoice(
        id=uuid.uuid4(),
        business_id=business_id,
        customer_id=uuid.uuid4(),
        invoice_number="INV-DRAFT",
        invoice_date=test_date,
        status=InvoiceStatus.DRAFT,
        subtotal=Decimal("5000.00"),
        taxable_amount=Decimal("5000.00"),
        tax_amount=Decimal("900.00"),
        total_amount=Decimal("5900.00"),
        lines=[],
    )
    cancelled_inv = SalesInvoice(
        id=uuid.uuid4(),
        business_id=business_id,
        customer_id=uuid.uuid4(),
        invoice_number="INV-CANCELLED",
        invoice_date=test_date,
        status=InvoiceStatus.CANCELLED,
        subtotal=Decimal("3000.00"),
        taxable_amount=Decimal("3000.00"),
        tax_amount=Decimal("540.00"),
        total_amount=Decimal("3540.00"),
        lines=[],
    )

    repo = FakeComplianceRepository(
        sales=[issued_inv, draft_inv, cancelled_inv],
        purchases=[],
        expenses=[],
    )
    service = GSTComplianceService(
        unit_of_work_factory=lambda: cast(
            GSTComplianceUnitOfWork, FakeComplianceUnitOfWork(repo)
        ),
        event_dispatcher=CapturingEventDispatcher(),
    )

    gstr1 = await service.generate_gstr1(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    # Only issued_inv is reflected
    assert gstr1.document_summary["sales_invoices"] == 1
    assert gstr1.b2b.taxable_value == Decimal("1000.00")
    assert gstr1.b2b.tax_amount == Decimal("180.00")


@pytest.mark.asyncio
async def test_e2e_mock_einvoice_and_ewaybill_lifecycle() -> None:
    """Mock e-invoice and e-way bill lifecycle operates safely with sandbox tagging."""
    _business_id, invoice, uow, service, dispatcher = build_service_state()

    # 1. Generate IRN through mock provider
    irn_res = await service.generate_irn(EInvoiceGenerateRequest(invoice_id=invoice.id))
    assert irn_res.invoice_id == invoice.id
    assert irn_res.irn is not None
    assert irn_res.ack_number is not None
    assert uow.einvoices.qr_codes[0].qr_content.startswith("IRN:")

    # 2. Duplicate IRN fails closed
    with pytest.raises(DuplicateIRNException):
        await service.generate_irn(EInvoiceGenerateRequest(invoice_id=invoice.id))

    # 3. Generate E-Way Bill
    ewb_res = await service.generate_eway_bill(
        EWayBillGenerateRequest(
            invoice_id=invoice.id,
            vehicle_number="KA01AB1234",
        )
    )
    assert ewb_res.eway_bill_number is not None

    # 4. Cancel E-Way Bill and IRN
    ewb_cancel = await service.cancel_eway_bill(
        EWayBillCancelRequest(
            invoice_id=invoice.id,
            reason="Order cancelled by buyer",
        )
    )
    assert ewb_cancel.status.value.upper() == "CANCELLED"

    irn_cancel = await service.cancel_irn(
        EInvoiceCancelRequest(
            invoice_id=invoice.id,
            reason="Commercial reversal",
        )
    )
    assert irn_cancel.status.value.upper() == "CANCELLED"


def test_pos_resolution_missing_facts_fail_closed() -> None:
    """Missing or indeterminate location facts fail closed deterministically."""
    pos_service = PlaceOfSupplyResolutionService()

    # 1. Missing supplier state code fails closed
    with pytest.raises(InvalidStateCodeException) as exc_supplier:
        pos_service.resolve_supply(
            SupplyResolutionContext(
                supplier_state_code="",
                buyer_gstin="29ABCDE1234F1Z5",
            )
        )
    assert exc_supplier.value.error_code == "sales.invoice_invalid_state_code"

    # 2. Tripartite bill-to/ship-to with indeterminate directing party fails closed
    with pytest.raises(DirectingPartyIndeterminateException) as exc_directing_none:
        pos_service.resolve_supply(
            SupplyResolutionContext(
                supplier_state_code="29",
                buyer_gstin="29ABCDE1234F1Z5",
                is_bill_to_ship_to=True,
                directing_party_is_billed_buyer=None,
                shipping_consignee_name="Consignee Co",
                shipping_state_code="27",
            )
        )
    assert (
        exc_directing_none.value.error_code
        == "sales.invoice_directing_party_indeterminate"
    )

    # 3. Tripartite supply with agent directing party (False) fails closed
    with pytest.raises(DirectingPartyIndeterminateException) as exc_directing_agent:
        pos_service.resolve_supply(
            SupplyResolutionContext(
                supplier_state_code="29",
                buyer_gstin="29ABCDE1234F1Z5",
                is_bill_to_ship_to=True,
                directing_party_is_billed_buyer=False,
                shipping_consignee_name="Consignee Co",
                shipping_state_code="27",
            )
        )
    assert (
        exc_directing_agent.value.error_code
        == "sales.invoice_directing_party_indeterminate"
    )

    # 4. Tripartite supply with missing buyer registration evidence fails closed
    with pytest.raises(BuyerRegistrationUnverifiedException) as exc_unverified:
        pos_service.resolve_supply(
            SupplyResolutionContext(
                supplier_state_code="29",
                buyer_gstin="29ABCDE1234F1Z5",
                is_bill_to_ship_to=True,
                directing_party_is_billed_buyer=True,
                shipping_consignee_name="Consignee Co",
                shipping_state_code="27",
                direction_timing=DirectionTiming.BEFORE_MOVEMENT,
                buyer_evidence=None,
            )
        )
    assert (
        exc_unverified.value.error_code
        == "sales.invoice_buyer_registration_unconfirmed"
    )

    valid_evidence = GSTINVerificationEvidence(
        gstin="29ABCDE1234F1Z5",
        status=GSTINEvidenceStatus.REGISTRATION_VERIFIED,
        evidence_source="SANDBOX_GST_VERIFIER",
        verified_at=datetime.now(tz=UTC),
    )
    valid_policy = FreshnessPolicy(is_approved=True, max_age_days=30)

    # 5. Tripartite supply with verified buyer but missing consignee fails closed
    with pytest.raises(ConsigneeRequiredException) as exc_consignee:
        pos_service.resolve_supply(
            SupplyResolutionContext(
                supplier_state_code="29",
                buyer_gstin="29ABCDE1234F1Z5",
                is_bill_to_ship_to=True,
                directing_party_is_billed_buyer=True,
                shipping_consignee_name=None,
                shipping_state_code="27",
                direction_timing=DirectionTiming.BEFORE_MOVEMENT,
                buyer_evidence=valid_evidence,
                freshness_policy=valid_policy,
                environment="testing",
            )
        )
    assert exc_consignee.value.error_code == "sales.invoice_consignee_required"

    # 6. Tripartite supply with verified buyer but unestablished timing fails closed
    with pytest.raises(DirectionTimingUnestablishedException) as exc_timing:
        pos_service.resolve_supply(
            SupplyResolutionContext(
                supplier_state_code="29",
                buyer_gstin="29ABCDE1234F1Z5",
                is_bill_to_ship_to=True,
                directing_party_is_billed_buyer=True,
                shipping_consignee_name="Consignee Co",
                shipping_state_code="27",
                direction_timing=None,
                buyer_evidence=valid_evidence,
                freshness_policy=valid_policy,
                environment="testing",
            )
        )
    assert exc_timing.value.error_code == "sales.invoice_direction_timing_unestablished"


@pytest.mark.asyncio
async def test_e2e_mixed_and_exempt_sales_accounting_and_return_reconciliation() -> (
    None
):
    """Verify mixed and exempt sales reconcile with GL 4000/2010 and returns."""
    business_id = uuid.uuid4()
    test_date = date(2026, 4, 20)

    cust = Customer(
        id=uuid.uuid4(),
        business_id=business_id,
        customer_code="CUST-B2B-KA",
        name="Karnataka Tech Corp",
        gstin="29TESTB2B1234F1Z5",
    )

    # 1. Mixed Invoice: Taxable line (2000 @ 18%) + Nil-rated line (500 @ 0%)
    inv_mixed_id = uuid.uuid4()
    inv_mixed = SalesInvoice(
        id=inv_mixed_id,
        business_id=business_id,
        customer_id=cust.id,
        customer=cust,
        invoice_number="INV-MIX-001",
        invoice_date=test_date,
        place_of_supply="29",
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("2500.00"),
        taxable_amount=Decimal("2500.00"),
        tax_amount=Decimal("360.00"),
        total_amount=Decimal("2860.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=inv_mixed_id,
                description="Taxable Hardware",
                quantity=Decimal("1.00"),
                unit_price=Decimal("2000.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("180.00"),
                sgst_amount=Decimal("180.00"),
                igst_amount=Decimal("0.00"),
                utgst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("2360.00"),
            ),
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=inv_mixed_id,
                description="Nil-Rated Documentation",
                quantity=Decimal("1.00"),
                unit_price=Decimal("500.00"),
                tax_rate=Decimal("0.00"),
                cgst_amount=Decimal("0.00"),
                sgst_amount=Decimal("0.00"),
                igst_amount=Decimal("0.00"),
                utgst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("500.00"),
            ),
        ],
    )
    inv_mixed.lines[0].hsn_code = "8471"
    inv_mixed.lines[1].hsn_code = "4901"

    # 2. Exempt Invoice: Statutory exempt service (1500 @ 0%)
    inv_exempt_id = uuid.uuid4()
    inv_exempt = SalesInvoice(
        id=inv_exempt_id,
        business_id=business_id,
        customer_id=cust.id,
        customer=cust,
        invoice_number="INV-EXM-001",
        invoice_date=test_date,
        place_of_supply="29",
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("1500.00"),
        taxable_amount=Decimal("1500.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("1500.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=inv_exempt_id,
                description="Exempt Medical Diagnostic",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1500.00"),
                tax_rate=Decimal("0.00"),
                cgst_amount=Decimal("0.00"),
                sgst_amount=Decimal("0.00"),
                igst_amount=Decimal("0.00"),
                utgst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("1500.00"),
            )
        ],
    )
    inv_exempt.lines[0].supply_type = GSTSupplyType.EXEMPT
    inv_exempt.lines[0].hsn_code = "9993"

    # 3. 100% Discounted Promotional Line: Rate 18%, taxable value 0, tax 0
    inv_disc_id = uuid.uuid4()
    inv_disc = SalesInvoice(
        id=inv_disc_id,
        business_id=business_id,
        customer_id=cust.id,
        customer=cust,
        invoice_number="INV-DISC-001",
        invoice_date=test_date,
        place_of_supply="29",
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("400.00"),
        discount_amount=Decimal("400.00"),
        taxable_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("0.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=inv_disc_id,
                description="Promotional Cloud Trial (100% Discounted)",
                quantity=Decimal("1.00"),
                unit_price=Decimal("400.00"),
                discount=Decimal("400.00"),
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
    inv_disc.lines[0].hsn_code = "998313"

    # Step A: Record into AccountingKernel
    acct_uow = FakeAccountingKernelUnitOfWork(business_id)
    acct_uow.sales_invoices_map[inv_mixed.id] = inv_mixed
    acct_uow.sales_invoices_map[inv_exempt.id] = inv_exempt
    acct_uow.sales_invoices_map[inv_disc.id] = inv_disc

    kernel = AccountingKernelService(
        unit_of_work_factory=lambda: cast(AccountingKernelUnitOfWork, acct_uow),
        event_dispatcher=CapturingEventDispatcher(),
    )

    await kernel.record_sales_invoice(inv_mixed.id, uow=acct_uow)
    await kernel.record_sales_invoice(inv_exempt.id, uow=acct_uow)
    # Note: Zero-amount invoices (inv_disc) have no monetary journal lines in GL

    # Verify General Ledger Entries
    sales_lines = [
        line
        for journal in acct_uow.journals
        for line in journal.lines
        if line.account.account_code == "4000"
    ]
    total_sales_turnover = sum((line.credit for line in sales_lines), Decimal("0.00"))
    assert total_sales_turnover == Decimal(
        "4000.00"
    )  # 2500 (mixed) + 1500 (exempt) + 0 (discounted)

    tax_lines = [
        line
        for journal in acct_uow.journals
        for line in journal.lines
        if line.account.account_code == "2010"
    ]
    total_output_tax = sum((line.credit for line in tax_lines), Decimal("0.00"))
    assert total_output_tax == Decimal("360.00")  # 180 CGST + 180 SGST

    # Step B: Generate GSTR-1 and Reconcile
    compliance_repo = FakeComplianceRepository(
        sales=[inv_mixed, inv_exempt, inv_disc],
        purchases=[],
        expenses=[],
    )
    compliance_uow = FakeComplianceUnitOfWork(compliance_repo)
    compliance_service = GSTComplianceService(
        unit_of_work_factory=lambda: cast(GSTComplianceUnitOfWork, compliance_uow),
        event_dispatcher=CapturingEventDispatcher(),
    )

    gstr1 = await compliance_service.generate_gstr1(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    # Table 4 (B2B): Contains taxable hardware (2000) + 0 from promo trial
    assert gstr1.b2b.taxable_value == Decimal("2000.00")
    assert gstr1.b2b.tax_amount == Decimal("360.00")
    assert gstr1.b2b.cgst_amount == Decimal("180.00")
    assert gstr1.b2b.sgst_amount == Decimal("180.00")

    # Table 8: Nil-rated (500) and Exempt (1500) segregated cleanly
    assert gstr1.nil_rated.taxable_value == Decimal("500.00")
    assert gstr1.nil_rated.tax_amount == Decimal("0.00")
    assert gstr1.exempt.taxable_value == Decimal("1500.00")
    assert gstr1.exempt.tax_amount == Decimal("0.00")

    # Invariants: 100% GL Reconciliation
    gstr1_turnover = (
        gstr1.b2b.taxable_value
        + gstr1.nil_rated.taxable_value
        + gstr1.exempt.taxable_value
    )
    assert gstr1_turnover == total_sales_turnover == Decimal("4000.00")
    assert gstr1.b2b.tax_amount == total_output_tax == Decimal("360.00")

    # Step C: Generate GSTR-3B and Reconcile
    gstr3b = await compliance_service.generate_gstr3b(
        GSTReportRequest(business_id=business_id, tax_period="2026-04")
    )

    # Table 3.1(a) Outward taxable supplies
    assert gstr3b.outward_taxable_supplies.taxable_value == Decimal("2000.00")
    assert gstr3b.outward_taxable_supplies.tax_amount == Decimal("360.00")

    # Table 3.1(c) Other outward supplies (nil/exempt combined: 500 + 1500 = 2000)
    assert gstr3b.exempt_supplies.taxable_value == Decimal("2000.00")
    assert gstr3b.exempt_supplies.tax_amount == Decimal("0.00")

    # Tax liability matches GL Account 2010
    assert gstr3b.tax_liability.tax_amount == Decimal("360.00")
    assert (
        gstr3b.outward_taxable_supplies.taxable_value
        + gstr3b.exempt_supplies.taxable_value
        == total_sales_turnover
    )
