"""Tests for Purchase Management services."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Self, cast

import pytest

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.common.events import Event, EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.purchases.events import (
    PurchaseApprovedEvent,
    PurchaseCancelledEvent,
    PurchaseCreatedEvent,
    PurchasePaidEvent,
    PurchaseReceivedEvent,
    SupplierCreatedEvent,
    SupplierDeactivatedEvent,
)
from app.modules.purchases.exceptions import (
    DuplicatePurchaseInvoiceException,
    DuplicateSupplierException,
    InvalidPurchaseStatusException,
    PurchaseValidationException,
    SupplierHasOpenPurchasesException,
)
from app.modules.purchases.models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseStatus,
    Supplier,
)
from app.modules.purchases.schemas import (
    PurchaseInvoiceCreate,
    PurchaseInvoiceLineCreate,
    PurchaseInvoiceLineUpdate,
    PurchaseInvoiceUpdate,
    SupplierCreate,
    SupplierUpdate,
)
from app.modules.purchases.services import PurchaseService, SupplierService
from app.modules.purchases.services.purchase_service import (
    PurchaseAccountingKernel,
    PurchaseLinePersistenceRepository,
    PurchasePersistenceRepository,
    PurchaseSupplierRepository,
    PurchaseUnitOfWork,
)
from app.modules.purchases.services.supplier_service import (
    SupplierPersistenceRepository,
    SupplierPurchaseRepository,
    SupplierUnitOfWork,
)

pytestmark = pytest.mark.asyncio


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


class FakeSupplierRepository:
    """Fake supplier repository for service tests."""

    def __init__(self, suppliers: list[Supplier] | None = None) -> None:
        """Initialize fake repository."""
        self.suppliers = suppliers or []

    async def create(
        self,
        request: SupplierCreate,
        *,
        business_id: uuid.UUID,
        supplier_code: str,
    ) -> Supplier:
        """Create a fake supplier."""
        supplier = Supplier(
            id=uuid.uuid4(),
            business_id=business_id,
            supplier_code=supplier_code,
            **request.model_dump(),
        )
        self.suppliers.append(supplier)
        return supplier

    async def get_by_id(self, supplier_id: uuid.UUID) -> Supplier | None:
        """Return supplier by id."""
        return next(
            (supplier for supplier in self.suppliers if supplier.id == supplier_id),
            None,
        )

    async def get_by_supplier_code(
        self,
        *,
        business_id: uuid.UUID,
        supplier_code: str,
    ) -> Supplier | None:
        """Return supplier by business code."""
        return next(
            (
                supplier
                for supplier in self.suppliers
                if supplier.business_id == business_id
                and supplier.supplier_code == supplier_code
            ),
            None,
        )

    async def get_by_gstin(
        self,
        *,
        business_id: uuid.UUID,
        gstin: str,
    ) -> Supplier | None:
        """Return supplier by GSTIN."""
        return next(
            (
                supplier
                for supplier in self.suppliers
                if supplier.business_id == business_id and supplier.gstin == gstin
            ),
            None,
        )

    async def list(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        sort: str | None = None,
    ) -> Page[Supplier]:
        """Return suppliers for a business."""
        _ = sort
        params = pagination or PaginationParams()
        items = [
            supplier
            for supplier in self.suppliers
            if supplier.business_id == business_id
        ]
        return Page.create(items=items, total=len(items), params=params)

    async def search(
        self,
        *,
        business_id: uuid.UUID,
        query: str,
        pagination: PaginationParams | None = None,
    ) -> Page[Supplier]:
        """Search suppliers by simple substring."""
        params = pagination or PaginationParams()
        normalized = query.casefold()
        items = [
            supplier
            for supplier in self.suppliers
            if supplier.business_id == business_id
            and (
                normalized in supplier.name.casefold()
                or normalized in supplier.supplier_code.casefold()
                or (
                    supplier.gstin is not None
                    and normalized in supplier.gstin.casefold()
                )
            )
        ]
        return Page.create(items=items, total=len(items), params=params)

    async def update(self, supplier: Supplier, request: SupplierUpdate) -> Supplier:
        """Update fake supplier."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(supplier, field_name, value)
        return supplier


class FakePurchaseRepository:
    """Fake purchase repository for service tests."""

    def __init__(
        self,
        purchases: list[PurchaseInvoice] | None = None,
        *,
        fail_create: bool = False,
    ) -> None:
        """Initialize fake repository."""
        self.purchases = purchases or []
        self.fail_create = fail_create

    async def create(
        self,
        request: PurchaseInvoiceCreate,
        *,
        business_id: uuid.UUID,
        purchase_number: str,
    ) -> PurchaseInvoice:
        """Create a fake purchase invoice."""
        if self.fail_create:
            raise RuntimeError("purchase create failed")
        purchase_id = uuid.uuid4()
        purchase = PurchaseInvoice(
            id=purchase_id,
            business_id=business_id,
            purchase_number=purchase_number,
            supplier_id=request.supplier_id,
            invoice_number=request.invoice_number,
            invoice_date=request.invoice_date,
            due_date=request.due_date,
            status=request.status,
            subtotal=request.subtotal,
            tax_amount=request.tax_amount,
            total_amount=request.total_amount,
            notes=request.notes,
            attachment_count=request.attachment_count,
            lines=[
                PurchaseInvoiceLine(
                    id=uuid.uuid4(),
                    purchase_invoice_id=purchase_id,
                    **line.model_dump(),
                )
                for line in request.lines
            ],
        )
        self.purchases.append(purchase)
        return purchase

    async def get_by_id(self, purchase_id: uuid.UUID) -> PurchaseInvoice | None:
        """Return purchase by id."""
        return next(
            (purchase for purchase in self.purchases if purchase.id == purchase_id),
            None,
        )

    async def get_by_purchase_number(
        self,
        *,
        business_id: uuid.UUID,
        purchase_number: str,
    ) -> PurchaseInvoice | None:
        """Return purchase by business purchase number."""
        return next(
            (
                purchase
                for purchase in self.purchases
                if purchase.business_id == business_id
                and purchase.purchase_number == purchase_number
            ),
            None,
        )

    async def list(
        self,
        *,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        sort: str | None = None,
        supplier_id: uuid.UUID | None = None,
        status: PurchaseStatus | None = None,
        invoice_date_from: date | None = None,
        invoice_date_to: date | None = None,
        due_date_from: date | None = None,
        due_date_to: date | None = None,
        purchase_number: str | None = None,
        invoice_number: str | None = None,
    ) -> Page[PurchaseInvoice]:
        """Return filtered purchases."""
        _ = sort
        _ = invoice_date_from
        _ = invoice_date_to
        _ = due_date_from
        _ = due_date_to
        _ = purchase_number
        params = pagination or PaginationParams()
        items = [
            purchase
            for purchase in self.purchases
            if purchase.business_id == business_id
            and (supplier_id is None or purchase.supplier_id == supplier_id)
            and (status is None or purchase.status == status)
            and (invoice_number is None or purchase.invoice_number == invoice_number)
        ]
        return Page.create(items=items, total=len(items), params=params)

    async def update(
        self,
        purchase_invoice: PurchaseInvoice,
        request: PurchaseInvoiceUpdate,
    ) -> PurchaseInvoice:
        """Update fake purchase."""
        update_data = request.model_dump(exclude_unset=True, exclude={"lines"})
        for field_name, value in update_data.items():
            setattr(purchase_invoice, field_name, value)
        return purchase_invoice


class FakePurchaseLineRepository:
    """Fake purchase line repository for service tests."""

    async def create(
        self,
        request: PurchaseInvoiceLineCreate,
        *,
        purchase_invoice_id: uuid.UUID,
    ) -> PurchaseInvoiceLine:
        """Create a fake purchase line."""
        return PurchaseInvoiceLine(
            id=uuid.uuid4(),
            purchase_invoice_id=purchase_invoice_id,
            **request.model_dump(),
        )

    async def delete(self, line: PurchaseInvoiceLine) -> None:
        """Soft-delete fake purchase line."""
        line.mark_deleted()


class FakePurchaseUnitOfWork:
    """Fake Unit of Work for purchase service tests."""

    def __init__(
        self,
        *,
        supplier_repository: FakeSupplierRepository,
        purchase_repository: FakePurchaseRepository | None = None,
    ) -> None:
        """Initialize fake repositories."""
        self.suppliers: SupplierPersistenceRepository | PurchaseSupplierRepository = (
            supplier_repository
        )
        self.purchase_invoices: (
            SupplierPurchaseRepository | PurchasePersistenceRepository
        ) = purchase_repository or FakePurchaseRepository()
        self.purchase_invoice_lines: PurchaseLinePersistenceRepository = (
            FakePurchaseLineRepository()
        )
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


class FakePurchaseAccountingKernel:
    """Fake accounting kernel for purchase service tests."""

    def __init__(self) -> None:
        """Initialize captured accounting calls."""
        self.purchase_ids: list[uuid.UUID] = []
        self.payment_purchase_ids: list[uuid.UUID] = []

    async def record_purchase_invoice(self, purchase_id: uuid.UUID) -> object:
        """Capture purchase invoice posting."""
        self.purchase_ids.append(purchase_id)
        return object()

    async def record_supplier_payment(self, purchase_id: uuid.UUID) -> object:
        """Capture supplier payment posting."""
        self.payment_purchase_ids.append(purchase_id)
        return object()


def build_supplier(*, is_active: bool = True) -> Supplier:
    """Build a supplier model."""
    return Supplier(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        supplier_code="SUP-0001",
        name="Aarav Wholesale",
        email="billing@example.com",
        gstin="29ABCDE1234F1Z5",
        is_active=is_active,
    )


def build_supplier_request() -> SupplierCreate:
    """Build a supplier create request."""
    return SupplierCreate(
        name="Aarav Wholesale",
        email="billing@example.com",
        phone="+919876543210",
        gstin="29ABCDE1234F1Z5",
        pan="ABCDE1234F",
        address="Bengaluru",
        payment_terms="Net 30",
    )


def build_purchase(
    *,
    status: PurchaseStatus = PurchaseStatus.DRAFT,
    supplier_id: uuid.UUID | None = None,
    business_id: uuid.UUID | None = None,
) -> PurchaseInvoice:
    """Build a purchase invoice model."""
    purchase_id = uuid.uuid4()
    return PurchaseInvoice(
        id=purchase_id,
        business_id=business_id or uuid.uuid4(),
        supplier_id=supplier_id or uuid.uuid4(),
        purchase_number="PUR-0001",
        invoice_number="SUP-INV-0001",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 6, 30),
        status=status,
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        attachment_count=1,
        lines=[
            PurchaseInvoiceLine(
                id=uuid.uuid4(),
                purchase_invoice_id=purchase_id,
                description="Office laptops",
                quantity=Decimal("2.00"),
                unit_cost=Decimal("500.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("1180.00"),
            )
        ],
    )


def build_purchase_request(supplier_id: uuid.UUID) -> PurchaseInvoiceCreate:
    """Build a purchase create request with advisory totals."""
    return PurchaseInvoiceCreate(
        supplier_id=supplier_id,
        invoice_number="SUP-INV-0001",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 6, 30),
        subtotal=Decimal("1.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("1.00"),
        lines=[
            PurchaseInvoiceLineCreate(
                description="Office laptops",
                quantity=Decimal("2.00"),
                unit_cost=Decimal("500.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("1.00"),
            )
        ],
    )


def build_supplier_service(
    uow: FakePurchaseUnitOfWork,
    dispatcher: CapturingEventDispatcher,
) -> SupplierService:
    """Build supplier service with fake dependencies."""
    return SupplierService(
        unit_of_work_factory=lambda: cast(SupplierUnitOfWork, uow),
        event_dispatcher=dispatcher,
    )


def build_purchase_service(
    uow: FakePurchaseUnitOfWork,
    dispatcher: CapturingEventDispatcher,
    accounting_kernel: FakePurchaseAccountingKernel | None = None,
) -> PurchaseService:
    """Build purchase service with fake dependencies."""
    return PurchaseService(
        unit_of_work_factory=lambda: cast(PurchaseUnitOfWork, uow),
        event_dispatcher=dispatcher,
        accounting_kernel=cast(
            PurchaseAccountingKernel | None,
            accounting_kernel,
        ),
    )


async def test_supplier_creation_and_event() -> None:
    """Supplier service creates suppliers and publishes an event."""
    dispatcher = CapturingEventDispatcher()
    uow = FakePurchaseUnitOfWork(supplier_repository=FakeSupplierRepository())
    service = build_supplier_service(uow, dispatcher)

    response = await service.create_supplier(
        build_supplier_request(),
        business_id=uuid.uuid4(),
    )

    assert response.supplier_code.startswith("SUP-")
    assert isinstance(dispatcher.events[0], SupplierCreatedEvent)
    assert uow.committed is True


async def test_duplicate_supplier_detection() -> None:
    """Supplier service rejects duplicate supplier names and GSTIN values."""
    supplier = build_supplier()
    uow = FakePurchaseUnitOfWork(
        supplier_repository=FakeSupplierRepository([supplier])
    )
    service = build_supplier_service(uow, CapturingEventDispatcher())

    with pytest.raises(DuplicateSupplierException):
        await service.create_supplier(
            build_supplier_request(),
            business_id=supplier.business_id,
        )

    other = build_supplier()
    other.name = "Different Supplier"
    gstin_uow = FakePurchaseUnitOfWork(
        supplier_repository=FakeSupplierRepository([other])
    )
    gstin_service = build_supplier_service(gstin_uow, CapturingEventDispatcher())
    with pytest.raises(DuplicateSupplierException):
        await gstin_service.create_supplier(
            build_supplier_request(),
            business_id=other.business_id,
        )


async def test_supplier_deactivation_rules() -> None:
    """Supplier service blocks deactivation when unpaid purchases exist."""
    supplier = build_supplier()
    open_purchase = build_purchase(
        status=PurchaseStatus.APPROVED,
        supplier_id=supplier.id,
        business_id=supplier.business_id,
    )
    blocked_uow = FakePurchaseUnitOfWork(
        supplier_repository=FakeSupplierRepository([supplier]),
        purchase_repository=FakePurchaseRepository([open_purchase]),
    )
    blocked_service = build_supplier_service(blocked_uow, CapturingEventDispatcher())

    with pytest.raises(SupplierHasOpenPurchasesException):
        await blocked_service.deactivate_supplier(supplier.id)

    clean_supplier = build_supplier()
    dispatcher = CapturingEventDispatcher()
    clean_uow = FakePurchaseUnitOfWork(
        supplier_repository=FakeSupplierRepository([clean_supplier])
    )
    clean_service = build_supplier_service(clean_uow, dispatcher)
    response = await clean_service.deactivate_supplier(clean_supplier.id)

    assert response.is_active is False
    assert isinstance(dispatcher.events[0], SupplierDeactivatedEvent)


async def test_purchase_creation_number_generation_totals_and_event() -> None:
    """Purchase service creates purchases, numbers, and totals."""
    supplier = build_supplier()
    dispatcher = CapturingEventDispatcher()
    uow = FakePurchaseUnitOfWork(
        supplier_repository=FakeSupplierRepository([supplier])
    )
    service = build_purchase_service(uow, dispatcher)

    response = await service.create_purchase(
        build_purchase_request(supplier.id),
        business_id=supplier.business_id,
    )

    assert response.purchase_number.startswith("PUR-20260601-")
    assert response.status == PurchaseStatus.DRAFT
    assert response.subtotal == Decimal("1000.00")
    assert response.tax_amount == Decimal("180.00")
    assert response.total_amount == Decimal("1180.00")
    assert response.lines[0].line_total == Decimal("1180.00")
    assert isinstance(dispatcher.events[0], PurchaseCreatedEvent)


async def test_purchase_invoice_number_uniqueness() -> None:
    """Purchase service rejects duplicate invoice numbers per supplier."""
    supplier = build_supplier()
    existing = build_purchase(supplier_id=supplier.id, business_id=supplier.business_id)
    uow = FakePurchaseUnitOfWork(
        supplier_repository=FakeSupplierRepository([supplier]),
        purchase_repository=FakePurchaseRepository([existing]),
    )
    service = build_purchase_service(uow, CapturingEventDispatcher())

    with pytest.raises(DuplicatePurchaseInvoiceException):
        await service.create_purchase(
            build_purchase_request(supplier.id),
            business_id=supplier.business_id,
        )


async def test_purchase_update_recalculates_lines() -> None:
    """Purchase service updates draft purchases and recalculates line totals."""
    supplier = build_supplier()
    purchase = build_purchase(supplier_id=supplier.id, business_id=supplier.business_id)
    dispatcher = CapturingEventDispatcher()
    uow = FakePurchaseUnitOfWork(
        supplier_repository=FakeSupplierRepository([supplier]),
        purchase_repository=FakePurchaseRepository([purchase]),
    )
    service = build_purchase_service(uow, dispatcher)

    response = await service.update_purchase(
        purchase.id,
        PurchaseInvoiceUpdate(
            notes="Updated",
            lines=[
                PurchaseInvoiceLineUpdate(
                    description="Monitor",
                    quantity=Decimal("1.00"),
                    unit_cost=Decimal("200.00"),
                    tax_rate=Decimal("10.00"),
                    line_total=Decimal("1.00"),
                )
            ],
        ),
    )

    assert response.notes == "Updated"
    assert response.subtotal == Decimal("200.00")
    assert response.tax_amount == Decimal("20.00")
    assert response.total_amount == Decimal("220.00")
    assert isinstance(dispatcher.events[0], PurchaseCreatedEvent) is False


async def test_purchase_status_transitions_and_events() -> None:
    """Purchase service enforces lifecycle transitions and publishes events."""
    supplier = build_supplier()
    purchase = build_purchase(supplier_id=supplier.id, business_id=supplier.business_id)
    dispatcher = CapturingEventDispatcher()
    uow = FakePurchaseUnitOfWork(
        supplier_repository=FakeSupplierRepository([supplier]),
        purchase_repository=FakePurchaseRepository([purchase]),
    )
    accounting_kernel = FakePurchaseAccountingKernel()
    service = build_purchase_service(uow, dispatcher, accounting_kernel)

    approved = await service.approve_purchase(purchase.id)
    received = await service.mark_received(purchase.id)
    paid = await service.mark_paid(purchase.id)

    assert approved.status == PurchaseStatus.APPROVED
    assert received.status == PurchaseStatus.RECEIVED
    assert paid.status == PurchaseStatus.PAID
    assert isinstance(dispatcher.events[0], PurchaseApprovedEvent)
    assert isinstance(dispatcher.events[1], PurchaseReceivedEvent)
    assert isinstance(dispatcher.events[2], PurchasePaidEvent)
    assert accounting_kernel.purchase_ids == [purchase.id]
    assert accounting_kernel.payment_purchase_ids == [purchase.id]


async def test_purchase_cancellation_rules() -> None:
    """Purchase service allows cancellation before paid only."""
    cancellable = build_purchase(status=PurchaseStatus.RECEIVED)
    dispatcher = CapturingEventDispatcher()
    uow = FakePurchaseUnitOfWork(
        supplier_repository=FakeSupplierRepository(),
        purchase_repository=FakePurchaseRepository([cancellable]),
    )
    service = build_purchase_service(uow, dispatcher)

    response = await service.cancel_purchase(cancellable.id)
    assert response.status == PurchaseStatus.CANCELLED
    assert isinstance(dispatcher.events[0], PurchaseCancelledEvent)

    paid = build_purchase(status=PurchaseStatus.PAID)
    paid_uow = FakePurchaseUnitOfWork(
        supplier_repository=FakeSupplierRepository(),
        purchase_repository=FakePurchaseRepository([paid]),
    )
    paid_service = build_purchase_service(paid_uow, CapturingEventDispatcher())
    with pytest.raises(InvalidPurchaseStatusException):
        await paid_service.cancel_purchase(paid.id)


async def test_purchase_validation_failures() -> None:
    """Purchase service validates supplier ownership and complete update lines."""
    supplier = build_supplier()
    purchase = build_purchase(
        supplier_id=supplier.id,
        business_id=supplier.business_id,
    )
    uow = FakePurchaseUnitOfWork(
        supplier_repository=FakeSupplierRepository([supplier]),
        purchase_repository=FakePurchaseRepository([purchase]),
    )
    service = build_purchase_service(uow, CapturingEventDispatcher())

    with pytest.raises(PurchaseValidationException):
        await service.create_purchase(
            build_purchase_request(supplier.id),
            business_id=uuid.uuid4(),
        )

    with pytest.raises(PurchaseValidationException):
        await service.update_purchase(
            purchase.id,
            PurchaseInvoiceUpdate(
                lines=[PurchaseInvoiceLineUpdate(description="Incomplete")]
            ),
        )


async def test_purchase_service_rolls_back_on_failure() -> None:
    """Unit of Work rolls back when purchase persistence fails."""
    supplier = build_supplier()
    uow = FakePurchaseUnitOfWork(
        supplier_repository=FakeSupplierRepository([supplier]),
        purchase_repository=FakePurchaseRepository(fail_create=True),
    )
    service = build_purchase_service(uow, CapturingEventDispatcher())

    with pytest.raises(RuntimeError):
        await service.create_purchase(
            build_purchase_request(supplier.id),
            business_id=supplier.business_id,
        )

    assert uow.committed is False
    assert uow.rolled_back is True
