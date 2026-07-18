"""Tests for Sales payment service."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Self

import pytest

from app.common.events import Event, EventDispatcher
from app.modules.sales.events import (
    PaymentDeletedEvent,
    PaymentRecordedEvent,
    PaymentUpdatedEvent,
)
from app.modules.sales.exceptions import (
    SalesInvalidInvoiceStatusException,
    SalesPaymentValidationException,
)
from app.modules.sales.models import InvoiceStatus, Payment, PaymentMethod, SalesInvoice
from app.modules.sales.schemas import PaymentCreateRequest
from app.modules.sales.services import PaymentService
from app.modules.sales.services.payment_service import (
    PaymentInvoiceRepository,
    PaymentPersistenceRepository,
)

pytestmark = pytest.mark.asyncio


class FakeInvoiceRepository:
    """Fake invoice repository for payment service tests."""

    def __init__(self, invoice: SalesInvoice | None) -> None:
        """Initialize with an invoice."""
        self.invoice = invoice

    async def get_by_id(self, invoice_id: uuid.UUID) -> SalesInvoice | None:
        """Return configured invoice by id."""
        if self.invoice is None or self.invoice.id != invoice_id:
            return None
        return self.invoice

    async def mark_status(
        self,
        invoice: SalesInvoice,
        status: InvoiceStatus,
    ) -> SalesInvoice:
        """Update invoice status."""
        invoice.status = status
        return invoice


class FakePaymentRepository:
    """Fake payment repository for payment service tests."""

    def __init__(
        self,
        *,
        existing_paid: Decimal = Decimal("0.00"),
        payment: Payment | None = None,
        fail_create: bool = False,
    ) -> None:
        """Initialize fake payment behavior."""
        self.existing_paid = existing_paid
        self.payment = payment
        self.fail_create = fail_create

    async def create(self, request: PaymentCreateRequest) -> Payment:
        """Create a fake payment."""
        if self.fail_create:
            raise RuntimeError("payment create failed")
        self.payment = Payment(
            id=uuid.uuid4(),
            invoice_id=request.invoice_id,
            payment_date=request.payment_date,
            amount=request.amount,
            payment_method=request.payment_method,
            reference_number=request.reference_number,
            notes=request.notes,
        )
        return self.payment

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        """Return configured payment by id."""
        if self.payment is None or self.payment.id != payment_id:
            return None
        return self.payment

    async def update(
        self,
        payment: Payment,
        request: PaymentCreateRequest,
    ) -> Payment:
        """Update fake payment fields."""
        payment.invoice_id = request.invoice_id
        payment.payment_date = request.payment_date
        payment.amount = request.amount
        payment.payment_method = request.payment_method
        payment.reference_number = request.reference_number
        payment.notes = request.notes
        return payment

    async def delete(self, payment: Payment) -> None:
        """Soft-delete fake payment."""
        payment.mark_deleted()

    async def total_paid(self, invoice_id: uuid.UUID) -> Decimal:
        """Return configured total paid."""
        _ = invoice_id
        return self.existing_paid


class FakePaymentUnitOfWork:
    """Fake Unit of Work for payment service tests."""

    def __init__(
        self,
        *,
        invoice_repository: FakeInvoiceRepository,
        payment_repository: FakePaymentRepository,
    ) -> None:
        """Initialize fake repositories."""
        self.sales_invoices: PaymentInvoiceRepository = invoice_repository
        self.payments: PaymentPersistenceRepository = payment_repository
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
    """Fake accounting kernel for payment integration tests."""

    def __init__(self) -> None:
        """Initialize captured calls."""
        self.payment_ids: list[uuid.UUID] = []

    async def record_customer_payment(self, payment_id: uuid.UUID) -> object:
        """Capture payment posting call."""
        self.payment_ids.append(payment_id)
        return object()


def build_invoice(
    *,
    status: InvoiceStatus = InvoiceStatus.ISSUED,
    total_amount: Decimal = Decimal("1000.00"),
) -> SalesInvoice:
    """Build an invoice model."""
    return SalesInvoice(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        invoice_number="INV-0001",
        invoice_date=date(2026, 4, 1),
        status=status,
        total_amount=total_amount,
    )


def build_payment_request(
    invoice_id: uuid.UUID,
    *,
    amount: Decimal = Decimal("500.00"),
) -> PaymentCreateRequest:
    """Build a valid payment request."""
    return PaymentCreateRequest(
        invoice_id=invoice_id,
        payment_date=date(2026, 4, 10),
        amount=amount,
        payment_method=PaymentMethod.UPI,
        reference_number="UPI-123",
    )


def build_service(
    uow: FakePaymentUnitOfWork,
    dispatcher: CapturingEventDispatcher,
) -> PaymentService:
    """Build payment service with fake dependencies."""
    return PaymentService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=dispatcher,
    )


async def test_record_payment() -> None:
    """Service records payment and publishes event."""
    invoice = build_invoice()
    dispatcher = CapturingEventDispatcher()
    uow = FakePaymentUnitOfWork(
        invoice_repository=FakeInvoiceRepository(invoice),
        payment_repository=FakePaymentRepository(),
    )
    service = build_service(uow, dispatcher)

    response = await service.record_payment(build_payment_request(invoice.id))

    assert response.amount == Decimal("500.00")
    assert invoice.status == InvoiceStatus.PARTIALLY_PAID
    assert uow.committed is True
    assert isinstance(dispatcher.events[0], PaymentRecordedEvent)


async def test_record_payment_calls_accounting_kernel() -> None:
    """Recording a payment delegates accounting posting to the kernel."""
    invoice = build_invoice()
    kernel = FakeAccountingKernel()
    uow = FakePaymentUnitOfWork(
        invoice_repository=FakeInvoiceRepository(invoice),
        payment_repository=FakePaymentRepository(),
    )
    service = PaymentService(
        unit_of_work_factory=lambda: uow,
        event_dispatcher=CapturingEventDispatcher(),
        accounting_kernel=kernel,
    )

    response = await service.record_payment(build_payment_request(invoice.id))

    assert kernel.payment_ids == [response.id]


async def test_partial_payment() -> None:
    """Partial payment marks invoice partially paid."""
    invoice = build_invoice(total_amount=Decimal("1000.00"))
    uow = FakePaymentUnitOfWork(
        invoice_repository=FakeInvoiceRepository(invoice),
        payment_repository=FakePaymentRepository(),
    )
    service = build_service(uow, CapturingEventDispatcher())

    await service.record_payment(
        build_payment_request(invoice.id, amount=Decimal("250.00"))
    )

    assert invoice.status == InvoiceStatus.PARTIALLY_PAID


async def test_full_payment() -> None:
    """Full payment marks invoice paid."""
    invoice = build_invoice(total_amount=Decimal("1000.00"))
    uow = FakePaymentUnitOfWork(
        invoice_repository=FakeInvoiceRepository(invoice),
        payment_repository=FakePaymentRepository(existing_paid=Decimal("500.00")),
    )
    service = build_service(uow, CapturingEventDispatcher())

    await service.record_payment(
        build_payment_request(invoice.id, amount=Decimal("500.00"))
    )

    assert invoice.status == InvoiceStatus.PAID


async def test_overpayment_rejected() -> None:
    """Payments greater than outstanding balance are rejected."""
    invoice = build_invoice(total_amount=Decimal("1000.00"))
    uow = FakePaymentUnitOfWork(
        invoice_repository=FakeInvoiceRepository(invoice),
        payment_repository=FakePaymentRepository(existing_paid=Decimal("900.00")),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(SalesPaymentValidationException):
        await service.record_payment(
            build_payment_request(invoice.id, amount=Decimal("200.00"))
        )

    assert uow.rolled_back is True


async def test_cancelled_invoice_rejected() -> None:
    """Cancelled invoices cannot receive payments."""
    invoice = build_invoice(status=InvoiceStatus.CANCELLED)
    uow = FakePaymentUnitOfWork(
        invoice_repository=FakeInvoiceRepository(invoice),
        payment_repository=FakePaymentRepository(),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(SalesInvalidInvoiceStatusException):
        await service.record_payment(build_payment_request(invoice.id))

    assert uow.rolled_back is True


async def test_draft_invoice_rejected() -> None:
    """Draft invoices cannot receive payments."""
    invoice = build_invoice(status=InvoiceStatus.DRAFT)
    uow = FakePaymentUnitOfWork(
        invoice_repository=FakeInvoiceRepository(invoice),
        payment_repository=FakePaymentRepository(),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(SalesInvalidInvoiceStatusException):
        await service.record_payment(build_payment_request(invoice.id))


async def test_update_payment() -> None:
    """Service updates payment and publishes event."""
    invoice = build_invoice()
    payment = Payment(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        payment_date=date(2026, 4, 10),
        amount=Decimal("200.00"),
        payment_method=PaymentMethod.CASH,
    )
    dispatcher = CapturingEventDispatcher()
    uow = FakePaymentUnitOfWork(
        invoice_repository=FakeInvoiceRepository(invoice),
        payment_repository=FakePaymentRepository(
            existing_paid=Decimal("200.00"),
            payment=payment,
        ),
    )
    service = build_service(uow, dispatcher)

    response = await service.update_payment(
        payment.id,
        build_payment_request(invoice.id, amount=Decimal("500.00")),
    )

    assert response.amount == Decimal("500.00")
    assert invoice.status == InvoiceStatus.PARTIALLY_PAID
    assert isinstance(dispatcher.events[0], PaymentUpdatedEvent)


async def test_delete_payment() -> None:
    """Service deletes payment, updates status, and publishes event."""
    invoice = build_invoice(status=InvoiceStatus.PARTIALLY_PAID)
    payment = Payment(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        payment_date=date(2026, 4, 10),
        amount=Decimal("500.00"),
        payment_method=PaymentMethod.UPI,
    )
    dispatcher = CapturingEventDispatcher()
    uow = FakePaymentUnitOfWork(
        invoice_repository=FakeInvoiceRepository(invoice),
        payment_repository=FakePaymentRepository(
            existing_paid=Decimal("500.00"),
            payment=payment,
        ),
    )
    service = build_service(uow, dispatcher)

    await service.delete_payment(payment.id)

    assert payment.is_deleted is True
    assert invoice.status == InvoiceStatus.ISSUED
    assert isinstance(dispatcher.events[0], PaymentDeletedEvent)


async def test_rollback_on_create_failure() -> None:
    """Unit of Work rolls back when payment persistence fails."""
    invoice = build_invoice()
    uow = FakePaymentUnitOfWork(
        invoice_repository=FakeInvoiceRepository(invoice),
        payment_repository=FakePaymentRepository(fail_create=True),
    )
    service = build_service(uow, CapturingEventDispatcher())

    with pytest.raises(RuntimeError):
        await service.record_payment(build_payment_request(invoice.id))

    assert uow.committed is False
    assert uow.rolled_back is True
