"""Canonical Sales domain and application workflow tests."""

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.main import create_app
from app.modules.catalog.models import CatalogItemStatus, ItemType
from app.modules.sales.canonical_schemas import (
    CanonicalInvoiceDraftRequest,
    CanonicalInvoiceLineRequest,
)
from app.modules.sales.canonical_service import CanonicalSalesInvoiceService
from app.modules.sales.domain import (
    InvoiceLifecycle,
    InvoiceLineValue,
)
from app.modules.sales.events import InvoiceCreatedEvent, InvoiceIssuedEvent
from app.modules.sales.exceptions import (
    SalesInvalidInvoiceStatusException,
    SalesInvoiceValidationException,
)
from app.modules.sales.financial_rules import SalesFinancialRulesEngine
from app.modules.sales.invoice_numbering import InvoiceNumberService
from app.modules.sales.models import (
    InvoiceNumberSequence,
    InvoiceStatus,
    SalesInvoiceLine,
)


class Sequence:
    value = 0

    async def reserve(
        self, business_id: uuid.UUID, financial_year: str, prefix: str
    ) -> int:
        self.value += 1
        return self.value


class Events:
    def __init__(self) -> None:
        self.events = []

    async def dispatch(self, event) -> None:
        self.events.append(event)


class CreditHook:
    def __init__(self) -> None:
        self.calls: list[tuple[Decimal, str]] = []

    async def validate(self, **values) -> None:
        self.calls.append((values["grand_total"], values["currency"]))


class Customers:
    def __init__(self, customer) -> None:
        self.customer = customer

    async def get_by_id(self, customer_id: uuid.UUID):
        return self.customer if customer_id == self.customer.id else None


class Catalog:
    def __init__(self, item) -> None:
        self.item = item

    async def get_by_id(self, item_id: uuid.UUID):
        return self.item if item_id == self.item.id else None


class Businesses:
    async def get_settings(self, business_id: uuid.UUID):
        return SimpleNamespace(currency="INR")


class Invoices:
    def __init__(self) -> None:
        self.invoice = None

    async def create(self, request):
        invoice_id = uuid.uuid4()
        lines = [
            SimpleNamespace(id=uuid.uuid4(), invoice_id=invoice_id, **line.model_dump())
            for line in request.lines
        ]
        self.invoice = SimpleNamespace(
            id=invoice_id,
            **request.model_dump(exclude={"lines"}),
            lines=lines,
            payments=[],
        )
        return self.invoice

    async def get_by_id(self, invoice_id):
        return self.invoice if self.invoice and self.invoice.id == invoice_id else None

    async def mark_status(self, invoice, status):
        invoice.status = status
        return invoice


class Uow:
    def __init__(self, customer, item) -> None:
        self.customers = Customers(customer)
        self.businesses = Businesses()
        self.catalog_items = Catalog(item)
        self.sales_invoices = Invoices()
        self.invoice_number_sequences = Sequence()
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.committed = True


def test_totals_are_server_authoritative() -> None:
    totals = SalesFinancialRulesEngine().calculate(
        [
            InvoiceLineValue(
                Decimal("2"), Decimal("100"), Decimal("10"), Decimal("18"), Decimal("1")
            )
        ],
    )
    assert totals.subtotal == Decimal("200.00")
    assert totals.discount_amount == Decimal("10.00")
    assert totals.tax.tax_amount == Decimal("34.20")
    assert totals.tax.cess_amount == Decimal("1.90")
    assert totals.round_off == Decimal("0.00")
    assert totals.grand_total == Decimal("226.10")


@pytest.mark.parametrize(
    "quantity,price", [(Decimal("0"), Decimal("1")), (Decimal("1"), Decimal("-1"))]
)
def test_invalid_line_values_are_rejected(quantity: Decimal, price: Decimal) -> None:
    with pytest.raises(SalesInvoiceValidationException):
        SalesFinancialRulesEngine().calculate(
            [InvoiceLineValue(quantity, price, Decimal("0"), Decimal("0"))]
        )


def test_discount_cannot_exceed_gross() -> None:
    with pytest.raises(SalesInvoiceValidationException):
        SalesFinancialRulesEngine().calculate(
            [InvoiceLineValue(Decimal("1"), Decimal("10"), Decimal("11"), Decimal("0"))]
        )


def test_terminal_invoice_states_are_immutable() -> None:
    lifecycle = InvoiceLifecycle()
    for state in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED):
        with pytest.raises(SalesInvalidInvoiceStatusException):
            lifecycle.ensure_editable(state)
        with pytest.raises(SalesInvalidInvoiceStatusException):
            lifecycle.validate(state, InvoiceStatus.ISSUED)


@pytest.mark.asyncio
async def test_invoice_numbers_are_financial_year_scoped_and_sequential() -> None:
    sequence = Sequence()
    service = InvoiceNumberService()
    business_id = uuid.uuid4()
    assert (
        await service.next_number(
            sequence, business_id=business_id, invoice_date=date(2026, 4, 1)
        )
        == "INV/2026-27/00001"
    )
    assert (
        await service.next_number(
            sequence, business_id=business_id, invoice_date=date(2026, 4, 1)
        )
        == "INV/2026-27/00002"
    )
    assert service.financial_year(date(2026, 3, 31)) == "2025-26"


@pytest.mark.asyncio
async def test_canonical_create_and_issue_use_catalog_without_side_effects() -> None:
    business_id, customer_id, item_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    customer = SimpleNamespace(
        id=customer_id,
        business_id=business_id,
        customer_code="C1",
        name="Customer",
        is_active=True,
    )
    item = SimpleNamespace(
        id=item_id,
        business_id=business_id,
        code="S1",
        name="Consulting",
        item_type=ItemType.SERVICE,
        status=CatalogItemStatus.ACTIVE,
        purchase_price=0,
        selling_price=100,
        default_unit="hour",
        sac_code="998311",
        gst_rate=18,
        cess_rate=0,
    )
    uow, events, credit = Uow(customer, item), Events(), CreditHook()
    service = CanonicalSalesInvoiceService(lambda: uow, events, credit_hooks=(credit,))
    response = await service.create_draft(
        CanonicalInvoiceDraftRequest(
            business_id=business_id,
            customer_id=customer_id,
            invoice_date=date(2026, 7, 20),
            currency="INR",
            payment_terms_days=30,
            lines=[
                CanonicalInvoiceLineRequest(
                    catalog_item_id=item_id, quantity=2, unit_price=100
                )
            ],
        )
    )
    assert response.invoice_number == "INV/2026-27/00001"
    assert response.total_amount == Decimal("236.00")
    assert response.currency == "INR"
    assert response.due_date == date(2026, 8, 19)
    assert response.lines[0].catalog_item_id == item_id
    assert isinstance(events.events[0], InvoiceCreatedEvent)
    assert credit.calls == [(Decimal("236.00"), "INR")]
    issued = await service.issue(response.id)
    assert issued.status == InvoiceStatus.ISSUED
    assert isinstance(events.events[1], InvoiceIssuedEvent)
    assert uow.committed is True


@pytest.mark.asyncio
async def test_catalog_business_isolation_is_enforced() -> None:
    business_id = uuid.uuid4()
    customer = SimpleNamespace(
        id=uuid.uuid4(),
        business_id=business_id,
        customer_code="C1",
        name="Customer",
        is_active=True,
    )
    item = SimpleNamespace(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        code="P1",
        name="Product",
        item_type=ItemType.PRODUCT,
        status=CatalogItemStatus.ACTIVE,
        purchase_price=0,
        selling_price=10,
        default_unit="each",
        hsn_code="8471",
        gst_rate=18,
        cess_rate=0,
    )
    service = CanonicalSalesInvoiceService(lambda: Uow(customer, item), Events())
    with pytest.raises(SalesInvoiceValidationException):
        await service.create_draft(
            CanonicalInvoiceDraftRequest(
                business_id=business_id,
                customer_id=customer.id,
                invoice_date=date.today(),
                lines=[
                    CanonicalInvoiceLineRequest(
                        catalog_item_id=item.id, quantity=1, unit_price=10
                    )
                ],
            )
        )


def test_canonical_api_contract_is_documented() -> None:
    paths = create_app(initialize_resources=False).openapi()["paths"]
    assert "post" in paths["/api/v1/sales/workflow/invoices"]
    assert "get" in paths["/api/v1/sales/workflow/invoices"]
    assert "patch" in paths["/api/v1/sales/workflow/invoices/{invoice_id}"]
    assert "post" in paths["/api/v1/sales/workflow/invoices/{invoice_id}/issue"]
    assert "post" in paths["/api/v1/sales/workflow/invoices/{invoice_id}/cancel"]


def test_additive_schema_keeps_legacy_catalog_reference_nullable() -> None:
    assert SalesInvoiceLine.__table__.c.catalog_item_id.nullable is True
    constraints = {
        constraint.name for constraint in InvoiceNumberSequence.__table__.constraints
    }
    assert "uq_sales_invoice_sequence_business_year" in constraints
