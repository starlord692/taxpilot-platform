"""Deterministic Sales intelligence and recommendation tests."""

import uuid
from collections.abc import Callable, Sequence
from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import pytest

from app.common.events import Event, EventDispatcher
from app.main import create_app
from app.modules.sales.events import InvoiceIntelligenceEvaluatedEvent
from app.modules.sales.intelligence import (
    AutomationReadiness,
    IntelligenceCatalogItem,
    IntelligenceEngine,
    IntelligenceInvoice,
    IntelligenceUnitOfWork,
    InvoiceIntelligenceResponse,
    RecommendationCategory,
    RecommendationSeverity,
    SalesIntelligenceService,
)

FULL_CONFIDENCE = 100
GST_FINDING_COUNT = 3
PRICING_FINDING_COUNT = 2
LOW_READINESS_CONFIDENCE = 40


def catalog_item(
    item_id: uuid.UUID,
    *,
    price: str = "100",
    gst_rate: str = "18",
    classified: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=item_id,
        selling_price=Decimal(price),
        gst_rate=Decimal(gst_rate),
        cess_rate=Decimal("0"),
        hsn_code="9983" if classified else None,
        sac_code=None,
    )


def line(
    item_id: uuid.UUID | None,
    *,
    price: str = "100",
    discount: str = "0",
    tax_rate: str = "18",
    cgst: str = "9",
    sgst: str = "9",
    igst: str = "0",
) -> SimpleNamespace:
    return SimpleNamespace(
        catalog_item_id=item_id,
        quantity=Decimal("1"),
        unit_price=Decimal(price),
        discount=Decimal(discount),
        tax_rate=Decimal(tax_rate),
        cgst_amount=Decimal(cgst),
        sgst_amount=Decimal(sgst),
        igst_amount=Decimal(igst),
        cess_amount=Decimal("0"),
    )


def invoice(
    invoice_id: uuid.UUID,
    customer_id: uuid.UUID,
    lines: list[SimpleNamespace],
    *,
    invoice_date: date = date(2026, 7, 20),
    total: str = "118",
    complete_customer: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=invoice_id,
        business_id=uuid.uuid4(),
        customer_id=customer_id,
        invoice_number=f"INV-{str(invoice_id)[:6]}",
        invoice_date=invoice_date,
        due_date=invoice_date,
        subtotal=Decimal("100"),
        discount_amount=Decimal("0"),
        taxable_amount=Decimal("100"),
        tax_amount=Decimal("18"),
        round_off=Decimal("0"),
        total_amount=Decimal(total),
        currency="INR",
        lines=lines,
        customer=SimpleNamespace(
            email="buyer@example.com" if complete_customer else None,
            phone="+919876543210" if complete_customer else None,
            gstin="27ABCDE1234F1Z5" if complete_customer else None,
            billing_address="Mumbai" if complete_customer else None,
        ),
    )


def categories(result: InvoiceIntelligenceResponse) -> list[RecommendationCategory]:
    return [item.category for item in result.recommendations]


def test_duplicate_detection_returns_confidence_match_and_explanation() -> None:
    item_id, customer_id = uuid.uuid4(), uuid.uuid4()
    current = invoice(uuid.uuid4(), customer_id, [line(item_id)])
    previous = invoice(uuid.uuid4(), customer_id, [line(item_id)])
    result = IntelligenceEngine().evaluate(
        current,
        catalog={item_id: catalog_item(item_id)},
        history=[previous],
        business_settings_complete=True,
        business_gst_registered=True,
    )
    duplicate = next(
        item
        for item in result.recommendations
        if item.category == RecommendationCategory.DUPLICATE
    )
    assert duplicate.confidence == FULL_CONFIDENCE
    assert duplicate.related_invoice_id == previous.id
    assert "same customer" in duplicate.explanation


def test_gst_anomalies_are_advisory() -> None:
    item_id, customer_id = uuid.uuid4(), uuid.uuid4()
    current = invoice(
        uuid.uuid4(),
        customer_id,
        [line(item_id, tax_rate="12", igst="18")],
    )
    result = IntelligenceEngine().evaluate(
        current,
        catalog={item_id: catalog_item(item_id, classified=False)},
        business_settings_complete=True,
        business_gst_registered=True,
    )
    gst = [
        item
        for item in result.recommendations
        if item.category == RecommendationCategory.GST
    ]
    assert len(gst) == GST_FINDING_COUNT
    assert any(item.severity == RecommendationSeverity.CRITICAL for item in gst)


def test_pricing_and_discount_anomalies_use_catalog_and_history() -> None:
    item_id, customer_id = uuid.uuid4(), uuid.uuid4()
    current = invoice(
        uuid.uuid4(),
        customer_id,
        [line(item_id, price="50", discount="15", cgst="3.15", sgst="3.15")],
        total="41.30",
    )
    current.subtotal = Decimal("50")
    current.discount_amount = Decimal("15")
    current.taxable_amount = Decimal("35")
    current.tax_amount = Decimal("6.30")
    previous = invoice(uuid.uuid4(), customer_id, [line(item_id, price="100")])
    result = IntelligenceEngine().evaluate(
        current,
        catalog={item_id: catalog_item(item_id, price="100")},
        history=[previous],
        business_settings_complete=True,
        business_gst_registered=True,
    )
    assert (
        categories(result).count(RecommendationCategory.PRICING)
        == PRICING_FINDING_COUNT
    )
    assert RecommendationCategory.DISCOUNT in categories(result)


def test_missing_information_and_mapping_reduce_readiness() -> None:
    customer_id = uuid.uuid4()
    current = invoice(uuid.uuid4(), customer_id, [line(None)], complete_customer=False)
    result = IntelligenceEngine().evaluate(
        current,
        catalog={},
        business_settings_complete=False,
        business_gst_registered=True,
    )
    assert RecommendationCategory.CUSTOMER in categories(result)
    assert RecommendationCategory.CATALOG in categories(result)
    assert result.automation_readiness.status == AutomationReadiness.NOT_READY
    assert result.automation_readiness.confidence == LOW_READINESS_CONFIDENCE


def test_consistent_complete_invoice_is_automation_ready() -> None:
    item_id, customer_id = uuid.uuid4(), uuid.uuid4()
    current = invoice(uuid.uuid4(), customer_id, [line(item_id)])
    result = IntelligenceEngine().evaluate(
        current,
        catalog={item_id: catalog_item(item_id)},
        business_settings_complete=True,
        business_gst_registered=True,
    )
    assert result.automation_readiness.status == AutomationReadiness.READY
    assert result.automation_readiness.confidence == FULL_CONFIDENCE


def test_financial_inconsistency_is_reported_without_mutation() -> None:
    item_id, customer_id = uuid.uuid4(), uuid.uuid4()
    current = invoice(uuid.uuid4(), customer_id, [line(item_id)], total="999")
    before = deepcopy(current)
    result = IntelligenceEngine().evaluate(
        current,
        catalog={item_id: catalog_item(item_id)},
        business_settings_complete=True,
        business_gst_registered=True,
    )
    finding = next(
        item
        for item in result.recommendations
        if item.category == RecommendationCategory.FINANCIAL
    )
    assert finding.severity == RecommendationSeverity.CRITICAL
    assert current.total_amount == before.total_amount
    assert current.lines[0].unit_price == before.lines[0].unit_price


def test_recommendations_api_is_separate_from_invoice_contract() -> None:
    paths = create_app(initialize_resources=False).openapi()["paths"]
    assert (
        "get" in paths["/api/v1/sales/workflow/invoices/{invoice_id}/recommendations"]
    )


@pytest.mark.asyncio
async def test_service_reads_context_and_publishes_advisory_event() -> None:
    item_id, customer_id = uuid.uuid4(), uuid.uuid4()
    current = invoice(uuid.uuid4(), customer_id, [line(item_id)])
    item = catalog_item(item_id)

    class Invoices:
        async def get_by_id(
            self, invoice_id: uuid.UUID
        ) -> IntelligenceInvoice | None:
            return current if invoice_id == current.id else None

        async def list_intelligence_history(
            self,
            *,
            business_id: uuid.UUID,
            customer_id: uuid.UUID,
            exclude_id: uuid.UUID,
        ) -> Sequence[IntelligenceInvoice]:
            return []

    class Catalog:
        async def get_by_ids(
            self, item_ids: set[uuid.UUID]
        ) -> Sequence[IntelligenceCatalogItem]:
            return [item] if item.id in item_ids else []

    class Businesses:
        async def get_settings(self, business_id: uuid.UUID) -> object | None:
            return SimpleNamespace(currency="INR")

        async def get_tax_profile(self, business_id: uuid.UUID) -> object | None:
            return SimpleNamespace(gst_registered=True)

    class Uow:
        sales_invoices = Invoices()
        catalog_items = Catalog()
        businesses = Businesses()

        async def __aenter__(self) -> "Uow":
            return self

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            traceback: object | None,
        ) -> None:
            return None

    class Events(EventDispatcher):
        def __init__(self) -> None:
            super().__init__()
            self.events: list[Event] = []

        async def dispatch(self, event: Event) -> None:
            self.events.append(event)

    events = Events()
    service = SalesIntelligenceService(
        # The nested fake implements the read-only IntelligenceUnitOfWork protocol.
        cast(Callable[[], IntelligenceUnitOfWork], Uow),
        events,
    )
    result = await service.evaluate(current.id)
    assert result.invoice_id == current.id
    assert len(events.events) == 1
    assert isinstance(events.events[0], InvoiceIntelligenceEvaluatedEvent)
