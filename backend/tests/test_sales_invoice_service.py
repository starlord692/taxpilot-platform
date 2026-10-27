"""Tests for Sales invoice service."""

import uuid
from datetime import date
from decimal import Decimal
from http import HTTPStatus
from typing import Any, Self

import pytest

from app.common.events import Event, EventDispatcher
from app.modules.catalog.models import (
    CatalogItem,
    CatalogItemStatus,
    InventoryItemProfile,
    ItemType,
)
from app.modules.gst.services.pos_resolution_service import (
    ConsigneeRequiredException,
    DirectingPartyIndeterminateException,
    DirectionTiming,
    DirectionTimingUnestablishedException,
    ShippingStateRequiredException,
)
from app.modules.sales.events import (
    InvoiceCancelledEvent,
    InvoiceCreatedEvent,
    InvoiceIssuedEvent,
    InvoicePaidEvent,
    InvoicePartiallyPaidEvent,
    InvoiceUpdatedEvent,
)
from app.modules.sales.exceptions import (
    SalesDuplicateInvoiceNumberException,
    SalesInvalidInvoiceStatusException,
    SalesInvoiceValidationException,
)
from app.modules.sales.models import (
    Customer,
    InvoiceStatus,
    SalesInvoice,
    SalesInvoiceLine,
)
from app.modules.sales.schemas import (
    CustomerCreateRequest,
    InvoiceCreateRequest,
    InvoiceLineRequest,
    InvoiceUpdateRequest,
)
from app.modules.sales.services import SalesInvoiceService
from app.modules.sales.services.invoice_service import (
    SalesCustomerRepository,
    SalesInvoiceLifecycleRepository,
)

pytestmark = pytest.mark.asyncio


class FakeCustomerRepository:
    """Fake customer repository for invoice service tests."""

    def __init__(self, customer: Customer | None) -> None:
        """Initialize with optional customer."""
        self.customer = customer
        self.created_customer: Customer | None = None

    async def create(self, request: CustomerCreateRequest) -> Customer:
        """Create a fake customer."""
        customer = Customer(
            id=uuid.uuid4(),
            business_id=request.business_id,
            customer_code=request.customer_code,
            name=request.name,
            email=request.email,
            is_active=True,
        )
        self.created_customer = customer
        self.customer = customer
        return customer

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        """Return configured customer by id."""
        if self.customer is None or self.customer.id != customer_id:
            return None
        return self.customer


class FakeInvoiceRepository:
    """Fake invoice repository for invoice service tests."""

    def __init__(
        self,
        *,
        duplicate_invoice: bool = False,
        fail_create: bool = False,
        invoice: SalesInvoice | None = None,
    ) -> None:
        """Initialize fake invoice behavior."""
        self.duplicate_invoice = duplicate_invoice
        self.fail_create = fail_create
        self.invoice = invoice

    async def create(self, request: InvoiceCreateRequest) -> SalesInvoice:
        """Create a fake invoice."""
        if self.fail_create:
            raise RuntimeError("create failed")
        invoice_id = uuid.uuid4()
        self.invoice = SalesInvoice(
            id=invoice_id,
            business_id=request.business_id,
            customer_id=request.customer_id,
            invoice_number=request.invoice_number,
            invoice_date=request.invoice_date,
            due_date=request.due_date,
            status=request.status,
            subtotal=request.subtotal,
            discount_amount=request.discount_amount,
            taxable_amount=request.taxable_amount,
            tax_amount=request.tax_amount,
            total_amount=request.total_amount,
            notes=request.notes,
            lines=[
                SalesInvoiceLine(
                    id=uuid.uuid4(),
                    invoice_id=invoice_id,
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount=line.discount,
                    tax_rate=line.tax_rate,
                    line_total=line.line_total,
                )
                for line in request.lines
            ],
        )
        return self.invoice

    async def update(
        self,
        invoice: SalesInvoice,
        request: InvoiceUpdateRequest,
    ) -> SalesInvoice:
        """Update fake invoice scalar fields."""
        for field_name, value in request.model_dump(
            exclude_unset=True,
            exclude={"lines"},
        ).items():
            setattr(invoice, field_name, value)
        return invoice

    async def get_by_id(self, invoice_id: uuid.UUID) -> SalesInvoice | None:
        """Return configured invoice by id."""
        if self.invoice is None or self.invoice.id != invoice_id:
            return None
        return self.invoice

    async def get_by_invoice_number(
        self,
        *,
        business_id: uuid.UUID,
        invoice_number: str,
    ) -> SalesInvoice | None:
        """Return duplicate invoice when configured."""
        _ = business_id
        _ = invoice_number
        if self.duplicate_invoice:
            return self.invoice or build_invoice()
        return None

    async def add_line(
        self,
        invoice: SalesInvoice,
        request: InvoiceLineRequest,
    ) -> SalesInvoiceLine:
        """Add a fake invoice line."""
        line = SalesInvoiceLine(
            id=uuid.uuid4(),
            invoice_id=invoice.id,
            description=request.description,
            quantity=request.quantity,
            unit_price=request.unit_price,
            discount=request.discount,
            tax_rate=request.tax_rate,
            line_total=request.line_total,
        )
        return line

    async def remove_line(self, line: SalesInvoiceLine) -> None:
        """Soft-delete a fake invoice line."""
        line.mark_deleted()

    async def mark_status(
        self,
        invoice: SalesInvoice,
        status: InvoiceStatus,
    ) -> SalesInvoice:
        """Update fake invoice status."""
        invoice.status = status
        return invoice


class FakeSalesInvoiceUnitOfWork:
    """Fake Unit of Work for invoice service tests."""

    def __init__(
        self,
        *,
        customer_repository: FakeCustomerRepository,
        invoice_repository: FakeInvoiceRepository,
    ) -> None:
        """Initialize fake repositories."""
        self.customers: SalesCustomerRepository = customer_repository
        self.sales_invoices: SalesInvoiceLifecycleRepository = invoice_repository
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        """Enter fake transaction scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Rollback uncommitted fake transactions."""
        if exc_type is not None or not self.committed:
            self.rolled_back = True

    async def commit(self) -> None:
        """Mark transaction committed."""
        self.committed = True


class CapturingEventDispatcher(EventDispatcher):
    """Event dispatcher that records dispatched events."""

    def __init__(self) -> None:
        """Initialize captured events."""
        super().__init__()
        self.events: list[Event] = []

    async def dispatch(self, event: Event) -> None:
        """Record and dispatch an event."""
        self.events.append(event)
        await super().dispatch(event)


class FakeAccountingKernel:
    """Fake accounting kernel for invoice integration tests."""

    def __init__(self) -> None:
        """Initialize captured calls."""
        self.invoice_ids: list[uuid.UUID] = []

    async def record_sales_invoice(
        self,
        invoice_id: uuid.UUID,
        uow: Any = None,
    ) -> object:
        """Capture invoice posting call."""
        self.invoice_ids.append(invoice_id)
        return object()


class FakeSalesStockEngine:
    """Fake stock engine for invoice integration tests."""

    def __init__(self) -> None:
        """Initialize captured calls."""
        self.invoices: list[SalesInvoice] = []
        self.stock_lines: list[Any] = []

    async def issue_sale(
        self,
        sales_invoice: SalesInvoice,
        *,
        warehouse_id: uuid.UUID | None = None,
        uow: Any = None,
    ) -> object:
        """Capture sale stock issue call."""
        self.invoices.append(sales_invoice)
        return object()

    async def issue_sale_lines(
        self,
        sales_invoice: SalesInvoice,
        lines: list[Any],
        *,
        uow: Any = None,
    ) -> object:
        """Capture sale stock issue lines call."""
        self.invoices.append(sales_invoice)
        self.stock_lines.extend(lines)
        return object()


def build_customer(business_id: uuid.UUID | None = None) -> Customer:
    """Build a customer model."""
    return Customer(
        id=uuid.uuid4(),
        business_id=business_id or uuid.uuid4(),
        customer_code="CUST-0001",
        name="Aarav Enterprises",
        is_active=True,
    )


def build_catalog_item(
    *,
    business_id: uuid.UUID,
    item_type: ItemType = ItemType.SERVICE,
    status: CatalogItemStatus = CatalogItemStatus.ACTIVE,
    name: str = "Monthly bookkeeping",
    legacy_product_id: uuid.UUID | None = None,
    default_warehouse_id: uuid.UUID | None = None,
    stock_tracking: bool = False,
) -> CatalogItem:
    """Build a catalog item model."""
    item_id = uuid.uuid4()
    item = CatalogItem(
        id=item_id,
        business_id=business_id,
        name=name,
        code="CAT-001",
        item_type=item_type,
        status=status,
        default_unit="PCS",
        gst_rate=Decimal("18.00"),
        selling_price=Decimal("500.00"),
    )
    if stock_tracking or legacy_product_id or default_warehouse_id:
        item.inventory_profile = InventoryItemProfile(
            id=uuid.uuid4(),
            catalog_item_id=item_id,
            stock_tracking=stock_tracking,
            legacy_product_id=legacy_product_id,
            default_warehouse_id=default_warehouse_id,
        )
    return item


def build_invoice(
    *,
    status: InvoiceStatus = InvoiceStatus.DRAFT,
    business_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    catalog_item: CatalogItem | None = None,
    with_catalog_line: bool = True,
) -> SalesInvoice:
    """Build an invoice model."""
    invoice_id = uuid.uuid4()
    b_id = business_id or uuid.uuid4()
    if with_catalog_line and catalog_item is None:
        catalog_item = build_catalog_item(business_id=b_id)

    line = SalesInvoiceLine(
        id=uuid.uuid4(),
        invoice_id=invoice_id,
        catalog_item_id=catalog_item.id if catalog_item else None,
        description=catalog_item.name if catalog_item else "Monthly bookkeeping",
        quantity=Decimal("2.00"),
        unit_price=Decimal("500.00"),
        discount=Decimal("50.00"),
        tax_rate=Decimal("18.00"),
        line_total=Decimal("1121.00"),
    )
    if catalog_item:
        line.catalog_item = catalog_item

    return SalesInvoice(
        id=invoice_id,
        business_id=b_id,
        customer_id=customer_id or uuid.uuid4(),
        invoice_number="INV-0001",
        invoice_date=date(2026, 4, 1),
        status=status,
        subtotal=Decimal("1000.00"),
        discount_amount=Decimal("50.00"),
        taxable_amount=Decimal("950.00"),
        tax_amount=Decimal("171.00"),
        total_amount=Decimal("1121.00"),
        lines=[line],
    )


def build_invoice_request(
    *,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    **kwargs: Any,
) -> InvoiceCreateRequest:
    """Build a valid invoice create request."""
    data: dict[str, Any] = {
        "business_id": business_id,
        "customer_id": customer_id,
        "invoice_number": "INV-0001",
        "invoice_date": date(2026, 4, 1),
        "due_date": date(2026, 4, 30),
        "subtotal": Decimal("0.00"),
        "discount_amount": Decimal("0.00"),
        "taxable_amount": Decimal("0.00"),
        "tax_amount": Decimal("0.00"),
        "total_amount": Decimal("0.00"),
        "lines": [
            InvoiceLineRequest(
                description="Monthly bookkeeping",
                quantity=Decimal("2.00"),
                unit_price=Decimal("500.00"),
                discount=Decimal("50.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("0.00"),
            )
        ],
    }
    data.update(kwargs)
    return InvoiceCreateRequest(**data)


def build_service(
    uow: FakeSalesInvoiceUnitOfWork,
    dispatcher: CapturingEventDispatcher,
) -> SalesInvoiceService:
    """Build invoice service with fake dependencies."""
    return SalesInvoiceService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=dispatcher,
    )


async def test_create_invoice() -> None:
    """Service creates invoice, calculates totals, commits, and emits event."""
    customer = build_customer()
    dispatcher = CapturingEventDispatcher()
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(customer),
        invoice_repository=FakeInvoiceRepository(),
    )
    service = build_service(uow, dispatcher)

    response = await service.create_invoice(
        build_invoice_request(
            business_id=customer.business_id,
            customer_id=customer.id,
        )
    )

    assert response.subtotal == Decimal("1000.00")
    assert response.discount_amount == Decimal("50.00")
    assert response.taxable_amount == Decimal("950.00")
    assert response.tax_amount == Decimal("171.00")
    assert response.total_amount == Decimal("1121.00")
    assert uow.committed is True
    assert isinstance(dispatcher.events[0], InvoiceCreatedEvent)


async def test_create_invoice_creates_customer_when_required() -> None:
    """Service can create the customer in the same transaction."""
    business_id = uuid.uuid4()
    missing_customer_id = uuid.uuid4()
    customer_repository = FakeCustomerRepository(None)
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=customer_repository,
        invoice_repository=FakeInvoiceRepository(),
    )
    service = build_service(uow, CapturingEventDispatcher())

    response = await service.create_invoice(
        build_invoice_request(
            business_id=business_id,
            customer_id=missing_customer_id,
        ),
        customer_request=CustomerCreateRequest(
            business_id=business_id,
            customer_code="CUST-0001",
            name="Aarav Enterprises",
        ),
    )

    assert customer_repository.created_customer is not None
    assert response.customer_id == customer_repository.created_customer.id


async def test_update_invoice() -> None:
    """Service updates invoice, recalculates supplied lines, and emits event."""
    invoice = build_invoice(status=InvoiceStatus.DRAFT)
    dispatcher = CapturingEventDispatcher()
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(build_customer(invoice.business_id)),
        invoice_repository=FakeInvoiceRepository(invoice=invoice),
    )
    service = build_service(uow, dispatcher)

    response = await service.update_invoice(
        invoice.id,
        InvoiceUpdateRequest(
            notes="Updated",
            lines=[
                InvoiceLineRequest(
                    description="Consulting",
                    quantity=Decimal("1.00"),
                    unit_price=Decimal("200.00"),
                    discount=Decimal("0.00"),
                    tax_rate=Decimal("10.00"),
                    line_total=Decimal("0.00"),
                )
            ],
        ),
    )

    assert response.notes == "Updated"
    assert response.subtotal == Decimal("200.00")
    assert response.tax_amount == Decimal("20.00")
    assert response.total_amount == Decimal("220.00")
    assert isinstance(dispatcher.events[0], InvoiceUpdatedEvent)


async def test_issue_invoice() -> None:
    """Service issues a draft invoice."""
    invoice = build_invoice(status=InvoiceStatus.DRAFT)
    dispatcher = CapturingEventDispatcher()
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(build_customer(invoice.business_id)),
        invoice_repository=FakeInvoiceRepository(invoice=invoice),
    )
    service = build_service(uow, dispatcher)

    response = await service.issue_invoice(invoice.id)

    assert response.status == InvoiceStatus.ISSUED
    assert isinstance(dispatcher.events[0], InvoiceIssuedEvent)


async def test_issue_invoice_calls_accounting_kernel() -> None:
    """Issuing an invoice delegates accounting posting to the kernel."""
    invoice = build_invoice(status=InvoiceStatus.DRAFT)
    kernel = FakeAccountingKernel()
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(build_customer(invoice.business_id)),
        invoice_repository=FakeInvoiceRepository(invoice=invoice),
    )
    service = SalesInvoiceService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=CapturingEventDispatcher(),
        accounting_kernel=kernel,
    )

    await service.issue_invoice(invoice.id)

    assert kernel.invoice_ids == [invoice.id]


async def test_issue_invoice_calls_stock_engine() -> None:
    """Issuing an invoice with a stock-tracked product delegates stock issuing
    to inventory engine."""
    b_id = uuid.uuid4()
    p_id = uuid.uuid4()
    wh_id = uuid.uuid4()
    cat_item = build_catalog_item(
        business_id=b_id,
        item_type=ItemType.PRODUCT,
        name="Server Hardware",
        stock_tracking=True,
        legacy_product_id=p_id,
        default_warehouse_id=wh_id,
    )
    invoice = build_invoice(
        status=InvoiceStatus.DRAFT,
        business_id=b_id,
        catalog_item=cat_item,
    )
    stock_engine = FakeSalesStockEngine()
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(build_customer(invoice.business_id)),
        invoice_repository=FakeInvoiceRepository(invoice=invoice),
    )
    service = SalesInvoiceService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=CapturingEventDispatcher(),
        stock_engine=stock_engine,
    )

    await service.issue_invoice(invoice.id)

    assert stock_engine.invoices == [invoice]
    assert len(stock_engine.stock_lines) == 1
    assert stock_engine.stock_lines[0].product_id == p_id
    assert stock_engine.stock_lines[0].warehouse_id == wh_id


async def test_issue_invoice_service_line_skips_stock_engine() -> None:
    """Issuing an invoice with only service lines does NOT call the stock engine."""
    b_id = uuid.uuid4()
    cat_item = build_catalog_item(
        business_id=b_id,
        item_type=ItemType.SERVICE,
        name="Cloud Consulting",
    )
    invoice = build_invoice(
        status=InvoiceStatus.DRAFT,
        business_id=b_id,
        catalog_item=cat_item,
    )
    stock_engine = FakeSalesStockEngine()
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(build_customer(invoice.business_id)),
        invoice_repository=FakeInvoiceRepository(invoice=invoice),
    )
    service = SalesInvoiceService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=CapturingEventDispatcher(),
        stock_engine=stock_engine,
    )

    await service.issue_invoice(invoice.id)

    assert len(stock_engine.invoices) == 0
    assert len(stock_engine.stock_lines) == 0


async def test_issue_invoice_rejects_unclassified_line() -> None:
    """Issuing fails closed if any line lacks a catalog_item_id."""
    invoice = build_invoice(status=InvoiceStatus.DRAFT, with_catalog_line=False)
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(build_customer(invoice.business_id)),
        invoice_repository=FakeInvoiceRepository(invoice=invoice),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(SalesInvoiceValidationException) as exc_info:
        await service.issue_invoice(invoice.id)
    assert "not linked to a catalog item" in str(exc_info.value)


async def test_issue_invoice_rejects_archived_catalog_item() -> None:
    """Issuing fails closed if a catalog item is archived."""
    b_id = uuid.uuid4()
    cat_item = build_catalog_item(
        business_id=b_id,
        status=CatalogItemStatus.ARCHIVED,
        name="Deprecated Widget",
    )
    invoice = build_invoice(
        status=InvoiceStatus.DRAFT,
        business_id=b_id,
        catalog_item=cat_item,
    )
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(build_customer(invoice.business_id)),
        invoice_repository=FakeInvoiceRepository(invoice=invoice),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(SalesInvoiceValidationException) as exc_info:
        await service.issue_invoice(invoice.id)
    assert "archived" in str(exc_info.value)


async def test_issue_invoice_rejects_stock_tracked_missing_product_mapping() -> None:
    """Issuing fails closed if stock-tracked item is missing legacy_product_id."""
    b_id = uuid.uuid4()
    cat_item = build_catalog_item(
        business_id=b_id,
        item_type=ItemType.PRODUCT,
        name="Untracked Router",
        stock_tracking=True,
        legacy_product_id=None,
        default_warehouse_id=uuid.uuid4(),
    )
    invoice = build_invoice(
        status=InvoiceStatus.DRAFT,
        business_id=b_id,
        catalog_item=cat_item,
    )
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(build_customer(invoice.business_id)),
        invoice_repository=FakeInvoiceRepository(invoice=invoice),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(SalesInvoiceValidationException) as exc_info:
        await service.issue_invoice(invoice.id)
    assert "linked inventory product mapping" in str(exc_info.value)


async def test_issue_invoice_rejects_stock_tracked_missing_warehouse() -> None:
    """Issuing fails closed if warehouse cannot be resolved for stock-tracked item."""
    b_id = uuid.uuid4()
    cat_item = build_catalog_item(
        business_id=b_id,
        item_type=ItemType.PRODUCT,
        name="Hardware No Warehouse",
        stock_tracking=True,
        legacy_product_id=uuid.uuid4(),
        default_warehouse_id=None,
    )
    invoice = build_invoice(
        status=InvoiceStatus.DRAFT,
        business_id=b_id,
        catalog_item=cat_item,
    )
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(build_customer(invoice.business_id)),
        invoice_repository=FakeInvoiceRepository(invoice=invoice),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(SalesInvoiceValidationException) as exc_info:
        await service.issue_invoice(invoice.id)
    assert "Warehouse could not be resolved" in str(exc_info.value)


async def test_cancel_invoice() -> None:
    """Service cancels a draft invoice successfully."""
    invoice = build_invoice(status=InvoiceStatus.DRAFT)
    dispatcher = CapturingEventDispatcher()
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(build_customer(invoice.business_id)),
        invoice_repository=FakeInvoiceRepository(invoice=invoice),
    )
    service = build_service(uow, dispatcher)

    response = await service.cancel_invoice(invoice.id)

    assert response.status == InvoiceStatus.CANCELLED
    assert isinstance(dispatcher.events[0], InvoiceCancelledEvent)


async def test_cancel_invoice_rejects_non_draft() -> None:
    """Service rejects cancellation of non-draft invoices."""
    for non_draft_status in (
        InvoiceStatus.ISSUED,
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.PAID,
    ):
        invoice = build_invoice(status=non_draft_status)
        dispatcher = CapturingEventDispatcher()
        uow = FakeSalesInvoiceUnitOfWork(
            customer_repository=FakeCustomerRepository(
                build_customer(invoice.business_id)
            ),
            invoice_repository=FakeInvoiceRepository(invoice=invoice),
        )
        service = build_service(uow, dispatcher)

        with pytest.raises(SalesInvalidInvoiceStatusException):
            await service.cancel_invoice(invoice.id)
        assert invoice.status == non_draft_status
        assert len(dispatcher.events) == 0


async def test_mark_partially_paid() -> None:
    """Service marks an issued invoice partially paid."""
    invoice = build_invoice(status=InvoiceStatus.ISSUED)
    dispatcher = CapturingEventDispatcher()
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(build_customer(invoice.business_id)),
        invoice_repository=FakeInvoiceRepository(invoice=invoice),
    )
    service = build_service(uow, dispatcher)

    response = await service.mark_partially_paid(invoice.id)

    assert response.status == InvoiceStatus.PARTIALLY_PAID
    assert isinstance(dispatcher.events[0], InvoicePartiallyPaidEvent)


async def test_mark_paid() -> None:
    """Service marks a partially paid invoice paid."""
    invoice = build_invoice(status=InvoiceStatus.PARTIALLY_PAID)
    dispatcher = CapturingEventDispatcher()
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(build_customer(invoice.business_id)),
        invoice_repository=FakeInvoiceRepository(invoice=invoice),
    )
    service = build_service(uow, dispatcher)

    response = await service.mark_paid(invoice.id)

    assert response.status == InvoiceStatus.PAID
    assert isinstance(dispatcher.events[0], InvoicePaidEvent)


async def test_duplicate_invoice_numbers_raise() -> None:
    """Service rejects duplicate invoice numbers."""
    customer = build_customer()
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(customer),
        invoice_repository=FakeInvoiceRepository(duplicate_invoice=True),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(SalesDuplicateInvoiceNumberException):
        await service.create_invoice(
            build_invoice_request(
                business_id=customer.business_id,
                customer_id=customer.id,
            )
        )

    assert uow.rolled_back is True


async def test_invalid_status_transition_raises() -> None:
    """Service rejects invalid status transitions."""
    invoice = build_invoice(status=InvoiceStatus.DRAFT)
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(build_customer(invoice.business_id)),
        invoice_repository=FakeInvoiceRepository(invoice=invoice),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(SalesInvalidInvoiceStatusException):
        await service.mark_paid(invoice.id)

    assert uow.rolled_back is True


async def test_rollback_on_create_failure() -> None:
    """Unit of Work rolls back when invoice creation fails."""
    customer = build_customer()
    uow = FakeSalesInvoiceUnitOfWork(
        customer_repository=FakeCustomerRepository(customer),
        invoice_repository=FakeInvoiceRepository(fail_create=True),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(RuntimeError):
        await service.create_invoice(
            build_invoice_request(
                business_id=customer.business_id,
                customer_id=customer.id,
            )
        )

    assert uow.committed is False
    assert uow.rolled_back is True


async def test_invoice_create_request_agency_direction_fails_closed() -> None:
    """Tripartite Section 10(1)(b) invoice request fails closed when directing
    party is not the billed buyer."""
    customer = build_customer()
    with pytest.raises(DirectingPartyIndeterminateException) as exc_info:
        build_invoice_request(
            business_id=customer.business_id,
            customer_id=customer.id,
            is_bill_to_ship_to=True,
            is_directing_party_billed_buyer=False,
            direction_timing=DirectionTiming.BEFORE_MOVEMENT,
            shipping_consignee_name="Consignee Ltd",
            shipping_state_code="33",
        )
    assert exc_info.value.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert exc_info.value.error_code == "sales.invoice_directing_party_indeterminate"


async def test_invoice_create_request_missing_facts_fails_closed() -> None:
    """Tripartite Section 10(1)(b) invoice request fails closed when required
    consignee, shipping state, or timing is omitted."""
    customer = build_customer()

    # Missing direction timing
    with pytest.raises(DirectionTimingUnestablishedException) as exc_info:
        build_invoice_request(
            business_id=customer.business_id,
            customer_id=customer.id,
            is_bill_to_ship_to=True,
            is_directing_party_billed_buyer=True,
            direction_timing=None,
            shipping_consignee_name="Consignee Ltd",
            shipping_state_code="33",
        )
    assert exc_info.value.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert exc_info.value.error_code == "sales.invoice_direction_timing_unestablished"

    # Missing consignee
    with pytest.raises(ConsigneeRequiredException) as exc_info:
        build_invoice_request(
            business_id=customer.business_id,
            customer_id=customer.id,
            is_bill_to_ship_to=True,
            is_directing_party_billed_buyer=True,
            direction_timing=DirectionTiming.BEFORE_MOVEMENT,
            shipping_consignee_name=None,
            shipping_state_code="33",
        )
    assert exc_info.value.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert exc_info.value.error_code == "sales.invoice_consignee_required"

    # Missing shipping state
    with pytest.raises(ShippingStateRequiredException) as exc_info:
        build_invoice_request(
            business_id=customer.business_id,
            customer_id=customer.id,
            is_bill_to_ship_to=True,
            is_directing_party_billed_buyer=True,
            direction_timing=DirectionTiming.BEFORE_MOVEMENT,
            shipping_consignee_name="Consignee Ltd",
            shipping_state_code=None,
        )
    assert exc_info.value.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert exc_info.value.error_code == "sales.invoice_shipping_state_required"


async def test_invoice_create_request_bill_to_ship_to_valid_succeeds() -> None:
    """Valid tripartite Section 10(1)(b) request instantiates cleanly."""
    customer = build_customer()
    validated = build_invoice_request(
        business_id=customer.business_id,
        customer_id=customer.id,
        is_bill_to_ship_to=True,
        is_directing_party_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Consignee Ltd",
        shipping_state_code="33",
    )
    assert validated.is_bill_to_ship_to is True
    assert validated.is_directing_party_billed_buyer is True
    assert validated.shipping_consignee_name == "Consignee Ltd"
    assert validated.shipping_state_code == "33"


async def test_invoice_create_request_omitted_directing_party_fails_closed() -> None:
    """Tripartite Section 10(1)(b) invoice request fails closed when directing
    party is omitted/indeterminate (default None)."""
    customer = build_customer()
    with pytest.raises(DirectingPartyIndeterminateException) as exc_info:
        build_invoice_request(
            business_id=customer.business_id,
            customer_id=customer.id,
            is_bill_to_ship_to=True,
            # is_directing_party_billed_buyer omitted (defaults to None)
            direction_timing=DirectionTiming.BEFORE_MOVEMENT,
            shipping_consignee_name="Consignee Ltd",
            shipping_state_code="33",
        )
    assert exc_info.value.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert exc_info.value.error_code == "sales.invoice_directing_party_indeterminate"


async def test_invoice_create_request_contradictory_facts_fails_closed() -> None:
    """Request declaring is_bill_to_ship_to=False but asserting directing party
    facts fails closed with DirectingPartyIndeterminateException."""
    customer = build_customer()
    with pytest.raises(DirectingPartyIndeterminateException) as exc_info:
        build_invoice_request(
            business_id=customer.business_id,
            customer_id=customer.id,
            is_bill_to_ship_to=False,
            is_directing_party_billed_buyer=True,
        )
    assert exc_info.value.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert exc_info.value.error_code == "sales.invoice_directing_party_indeterminate"


async def test_invoice_update_request_omitted_directing_party_fails_closed() -> None:
    """Updating invoice to bill-to/ship-to without affirming directing party
    fails closed."""
    with pytest.raises(DirectingPartyIndeterminateException) as exc_info:
        InvoiceUpdateRequest(
            is_bill_to_ship_to=True,
            # is_directing_party_billed_buyer is None
            direction_timing=DirectionTiming.BEFORE_MOVEMENT,
            shipping_consignee_name="Consignee Ltd",
            shipping_state_code="33",
        )
    assert exc_info.value.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert exc_info.value.error_code == "sales.invoice_directing_party_indeterminate"


async def test_invoice_update_request_contradictory_facts_fails_closed() -> None:
    """Updating invoice with is_bill_to_ship_to=False but asserting direction
    facts fails closed."""
    with pytest.raises(DirectingPartyIndeterminateException) as exc_info:
        InvoiceUpdateRequest(
            is_bill_to_ship_to=False,
            is_directing_party_billed_buyer=True,
        )
    assert exc_info.value.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert exc_info.value.error_code == "sales.invoice_directing_party_indeterminate"


async def test_invoice_update_request_valid_bill_to_ship_to_succeeds() -> None:
    """Valid bill-to/ship-to update request succeeds cleanly."""
    update_req = InvoiceUpdateRequest(
        is_bill_to_ship_to=True,
        is_directing_party_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Consignee Ltd",
        shipping_state_code="33",
    )
    assert update_req.is_bill_to_ship_to is True
    assert update_req.is_directing_party_billed_buyer is True


async def test_invoice_update_standard_unspecified_party_succeeds() -> None:
    """Standard update request with unspecified directing party succeeds."""
    update_req = InvoiceUpdateRequest(
        notes="Updated notes",
    )
    assert update_req.is_bill_to_ship_to is None
    assert update_req.is_directing_party_billed_buyer is None
    assert update_req.notes == "Updated notes"
