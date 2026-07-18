"""Tests for GST calculation engine and module integration."""

import uuid
from decimal import Decimal
from typing import cast

import pytest

from app.common.events import Event, EventDispatcher
from app.modules.accounting.kernel import AccountingKernelService
from app.modules.gst.events import GSTCalculatedEvent
from app.modules.gst.models import GSTRoundingMethod
from app.modules.gst.services import (
    GSTCalculationLineInput,
    GSTCalculationRequest,
    GSTCalculationService,
    GSTSupplyType,
)
from app.modules.sales.schemas import InvoiceLineRequest
from app.modules.sales.services.invoice_service import SalesInvoiceService


def unused_unit_of_work_factory() -> object:
    """Return a placeholder Unit of Work for private calculation tests."""
    return object()


class CapturingEventDispatcher(EventDispatcher):
    """Event dispatcher that records dispatched events."""

    def __init__(self) -> None:
        """Initialize captured event storage."""
        super().__init__()
        self.events: list[Event] = []

    async def dispatch(self, event: Event) -> None:
        """Capture and dispatch an event."""
        self.events.append(event)
        await super().dispatch(event)


def test_calculate_line_intra_state_tax_exclusive() -> None:
    """Intra-state GST splits tax into CGST and SGST."""
    service = GSTCalculationService()

    result = service.calculate_line(
        GSTCalculationLineInput(
            description="Consulting",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            supply_type=GSTSupplyType.INTRA_STATE,
        )
    )

    assert result.taxable_value == Decimal("1000.00")
    assert result.cgst_amount == Decimal("90.00")
    assert result.sgst_amount == Decimal("90.00")
    assert result.igst_amount == Decimal("0.00")
    assert result.line_total == Decimal("1180.00")


def test_calculate_line_inter_state_tax_exclusive() -> None:
    """Inter-state GST posts tax as IGST."""
    service = GSTCalculationService()

    result = service.calculate_line(
        GSTCalculationLineInput(
            description="Consulting",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            supply_type=GSTSupplyType.INTER_STATE,
        )
    )

    assert result.cgst_amount == Decimal("0.00")
    assert result.sgst_amount == Decimal("0.00")
    assert result.igst_amount == Decimal("180.00")
    assert result.line_total == Decimal("1180.00")


def test_calculate_line_tax_inclusive() -> None:
    """Tax-inclusive price backs tax out of the line amount."""
    service = GSTCalculationService()

    result = service.calculate_line(
        GSTCalculationLineInput(
            description="Inclusive item",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("1180.00"),
            tax_rate=Decimal("18.00"),
            supply_type=GSTSupplyType.INTRA_STATE,
        ),
        tax_inclusive=True,
    )

    assert result.taxable_value == Decimal("1000.00")
    assert result.tax_amount == Decimal("180.00")
    assert result.line_total == Decimal("1180.00")


@pytest.mark.parametrize(
    "supply_type",
    [
        GSTSupplyType.ZERO_RATED,
        GSTSupplyType.EXEMPT,
        GSTSupplyType.NIL_RATED,
    ],
)
def test_zero_exempt_and_nil_rated_lines_have_no_tax(
    supply_type: GSTSupplyType,
) -> None:
    """Zero-rated, exempt, and nil-rated supplies calculate no GST."""
    service = GSTCalculationService()

    result = service.calculate_line(
        GSTCalculationLineInput(
            description="No tax item",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            supply_type=supply_type,
        )
    )

    assert result.tax_amount == Decimal("0.00")
    assert result.line_total == Decimal("1000.00")


def test_reverse_charge_and_composition_flags() -> None:
    """RCM marks ITC unavailable and composition suppresses tax."""
    service = GSTCalculationService()

    reverse_charge = service.calculate_line(
        GSTCalculationLineInput(
            description="RCM service",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            reverse_charge=True,
        )
    )
    composition = service.calculate_line(
        GSTCalculationLineInput(
            description="Composition supply",
            quantity=Decimal("1.00"),
            unit_amount=Decimal("1000.00"),
            tax_rate=Decimal("18.00"),
            composition_dealer=True,
        )
    )

    assert reverse_charge.tax_amount == Decimal("180.00")
    assert reverse_charge.input_tax_credit_available is False
    assert composition.tax_amount == Decimal("0.00")


@pytest.mark.asyncio
async def test_calculate_invoice_multiline_rounding_and_event() -> None:
    """Invoice calculation handles multiple lines, rounding, and events."""
    dispatcher = CapturingEventDispatcher()
    service = GSTCalculationService(dispatcher)
    business_id = uuid.uuid4()

    result = await service.calculate_invoice(
        GSTCalculationRequest(
            business_id=business_id,
            source_type="sales_invoice",
            lines=[
                GSTCalculationLineInput(
                    description="Item 1",
                    quantity=Decimal("1.00"),
                    unit_amount=Decimal("99.99"),
                    tax_rate=Decimal("18.00"),
                ),
                GSTCalculationLineInput(
                    description="Item 2",
                    quantity=Decimal("2.00"),
                    unit_amount=Decimal("50.00"),
                    tax_rate=Decimal("5.00"),
                ),
            ],
            rounding_method=GSTRoundingMethod.NEAREST,
        )
    )

    assert result.taxable_value == Decimal("199.99")
    assert result.tax_amount == Decimal("23.00")
    assert result.total_amount == Decimal("222.99")
    assert isinstance(dispatcher.events[0], GSTCalculatedEvent)


def test_sales_service_total_calculation_delegates_to_gst_engine() -> None:
    """Sales service stores GST component breakdown on prepared lines."""
    service = SalesInvoiceService(
        unit_of_work_factory=unused_unit_of_work_factory,  # type: ignore[arg-type]
        event_dispatcher=EventDispatcher(),
        gst_calculation_service=GSTCalculationService(),
    )

    totals = service._calculate_totals(  # noqa: SLF001
        [
            InvoiceLineRequest(
                description="Monthly bookkeeping",
                quantity=Decimal("2.00"),
                unit_price=Decimal("500.00"),
                discount=Decimal("50.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("0.00"),
            )
        ]
    )
    lines = cast(list[InvoiceLineRequest], totals["lines"])
    line = lines[0]

    assert totals["taxable_amount"] == Decimal("950.00")
    assert totals["tax_amount"] == Decimal("171.00")
    assert line.cgst_amount == Decimal("85.50")
    assert line.sgst_amount == Decimal("85.50")


def test_accounting_kernel_consumes_gst_components() -> None:
    """Accounting kernel aggregates line GST components for tax journal lines."""
    kernel = AccountingKernelService(
        unit_of_work_factory=unused_unit_of_work_factory,  # type: ignore[arg-type]
        event_dispatcher=EventDispatcher(),
    )
    line = type(
        "Line",
        (),
        {
            "cgst_amount": Decimal("90.00"),
            "sgst_amount": Decimal("90.00"),
            "igst_amount": Decimal("0.00"),
            "cess_amount": Decimal("5.00"),
        },
    )()

    components = kernel._tax_components(  # noqa: SLF001
        [line],
        fallback_tax_amount=Decimal("0.00"),
    )

    assert components["CGST"] == Decimal("90.00")
    assert components["SGST"] == Decimal("90.00")
    assert components["CESS"] == Decimal("5.00")
