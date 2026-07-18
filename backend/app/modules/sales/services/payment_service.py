"""Sales payment service."""

import uuid
from collections.abc import Callable
from decimal import Decimal
from typing import Protocol

from app.common.events import EventDispatcher
from app.modules.sales.events import (
    PaymentDeletedEvent,
    PaymentRecordedEvent,
    PaymentUpdatedEvent,
)
from app.modules.sales.exceptions import (
    SalesInvalidInvoiceStatusException,
    SalesInvoiceNotFoundException,
    SalesPaymentNotFoundException,
    SalesPaymentValidationException,
)
from app.modules.sales.models import InvoiceStatus, Payment, SalesInvoice
from app.modules.sales.schemas import PaymentCreateRequest, PaymentResponse

ZERO_AMOUNT = Decimal("0.00")


class PaymentInvoiceRepository(Protocol):
    """Invoice repository behavior required by payment service."""

    async def get_by_id(self, invoice_id: uuid.UUID) -> SalesInvoice | None:
        """Return an invoice by UUID."""
        ...

    async def mark_status(
        self,
        invoice: SalesInvoice,
        status: InvoiceStatus,
    ) -> SalesInvoice:
        """Mark invoice status."""
        ...


class PaymentPersistenceRepository(Protocol):
    """Payment repository behavior required by payment service."""

    async def create(self, request: PaymentCreateRequest) -> Payment:
        """Create a payment."""
        ...

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        """Return a payment by UUID."""
        ...

    async def update(
        self,
        payment: Payment,
        request: PaymentCreateRequest,
    ) -> Payment:
        """Update a payment."""
        ...

    async def delete(self, payment: Payment) -> None:
        """Delete a payment."""
        ...

    async def total_paid(self, invoice_id: uuid.UUID) -> Decimal:
        """Return total paid for an invoice."""
        ...


class PaymentUnitOfWork(Protocol):
    """Unit of Work contract required by payment operations."""

    sales_invoices: PaymentInvoiceRepository
    payments: PaymentPersistenceRepository

    async def __aenter__(self) -> "PaymentUnitOfWork":
        """Enter the payment transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the payment transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit payment changes."""
        ...


UnitOfWorkFactory = Callable[[], PaymentUnitOfWork]


class PaymentAccountingKernel(Protocol):
    """Accounting integration behavior required by payment service."""

    async def record_customer_payment(self, payment_id: uuid.UUID) -> object:
        """Post a customer payment to accounting."""
        ...


class PaymentService:
    """Coordinate sales payment lifecycle operations."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
        accounting_kernel: PaymentAccountingKernel | None = None,
    ) -> None:
        """Initialize service dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._accounting_kernel = accounting_kernel

    async def record_payment(self, request: PaymentCreateRequest) -> PaymentResponse:
        """Record a payment against an invoice."""
        validated_request = PaymentCreateRequest.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            invoice = await self._get_payable_invoice(uow, validated_request.invoice_id)
            paid_before = await uow.payments.total_paid(invoice.id)
            self._ensure_not_overpaid(
                invoice,
                payment_amount=validated_request.amount,
                paid_excluding_payment=paid_before,
            )

            payment = await uow.payments.create(validated_request)
            await self._sync_invoice_payment_status(
                uow,
                invoice,
                paid_before + payment.amount,
            )
            await self._event_dispatcher.dispatch(
                PaymentRecordedEvent(
                    payment_id=payment.id,
                    invoice_id=invoice.id,
                    business_id=invoice.business_id,
                )
            )
            await uow.commit()

        if self._accounting_kernel is not None:
            await self._accounting_kernel.record_customer_payment(payment.id)
        return PaymentResponse.model_validate(payment)

    async def update_payment(
        self,
        payment_id: uuid.UUID,
        request: PaymentCreateRequest,
    ) -> PaymentResponse:
        """Update a payment and invoice status."""
        validated_request = PaymentCreateRequest.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            payment = await self._get_existing_payment(uow, payment_id)
            invoice = await self._get_payable_invoice(uow, validated_request.invoice_id)
            paid_before = await uow.payments.total_paid(invoice.id)
            paid_without_payment = paid_before
            if payment.invoice_id == invoice.id:
                paid_without_payment -= payment.amount

            self._ensure_not_overpaid(
                invoice,
                payment_amount=validated_request.amount,
                paid_excluding_payment=paid_without_payment,
            )
            payment = await uow.payments.update(payment, validated_request)
            await self._sync_invoice_payment_status(
                uow,
                invoice,
                paid_without_payment + payment.amount,
            )
            await self._event_dispatcher.dispatch(
                PaymentUpdatedEvent(
                    payment_id=payment.id,
                    invoice_id=invoice.id,
                    business_id=invoice.business_id,
                )
            )
            await uow.commit()

        return PaymentResponse.model_validate(payment)

    async def delete_payment(self, payment_id: uuid.UUID) -> None:
        """Soft-delete a payment and update invoice status."""
        async with self._unit_of_work_factory() as uow:
            payment = await self._get_existing_payment(uow, payment_id)
            invoice = await self._get_payable_invoice(uow, payment.invoice_id)
            paid_before = await uow.payments.total_paid(invoice.id)
            remaining_paid = max(paid_before - payment.amount, ZERO_AMOUNT)

            await uow.payments.delete(payment)
            await self._sync_invoice_payment_status(uow, invoice, remaining_paid)
            await self._event_dispatcher.dispatch(
                PaymentDeletedEvent(
                    payment_id=payment.id,
                    invoice_id=invoice.id,
                    business_id=invoice.business_id,
                )
            )
            await uow.commit()

    async def _get_existing_payment(
        self,
        uow: PaymentUnitOfWork,
        payment_id: uuid.UUID,
    ) -> Payment:
        """Return a payment or raise not found."""
        payment = await uow.payments.get_by_id(payment_id)
        if payment is None:
            raise SalesPaymentNotFoundException(
                "Payment not found",
                details={"payment_id": str(payment_id)},
            )
        return payment

    async def _get_payable_invoice(
        self,
        uow: PaymentUnitOfWork,
        invoice_id: uuid.UUID,
    ) -> SalesInvoice:
        """Return invoice or raise when it cannot accept payments."""
        invoice = await uow.sales_invoices.get_by_id(invoice_id)
        if invoice is None:
            raise SalesInvoiceNotFoundException(
                "Invoice not found",
                details={"invoice_id": str(invoice_id)},
            )
        if invoice.status == InvoiceStatus.CANCELLED:
            raise SalesInvalidInvoiceStatusException(
                "Cancelled invoices cannot receive payments",
                details={"invoice_id": str(invoice_id)},
            )
        if invoice.status == InvoiceStatus.DRAFT:
            raise SalesInvalidInvoiceStatusException(
                "Draft invoices cannot receive payments",
                details={"invoice_id": str(invoice_id)},
            )
        return invoice

    def _ensure_not_overpaid(
        self,
        invoice: SalesInvoice,
        *,
        payment_amount: Decimal,
        paid_excluding_payment: Decimal,
    ) -> None:
        """Raise when payment exceeds outstanding invoice balance."""
        if payment_amount <= ZERO_AMOUNT:
            raise SalesPaymentValidationException("Payment amount must be positive")
        outstanding = invoice.total_amount - paid_excluding_payment
        if payment_amount > outstanding:
            raise SalesPaymentValidationException(
                "Payment amount exceeds outstanding invoice balance",
                details={
                    "invoice_id": str(invoice.id),
                    "outstanding": str(outstanding),
                    "payment_amount": str(payment_amount),
                },
            )

    async def _sync_invoice_payment_status(
        self,
        uow: PaymentUnitOfWork,
        invoice: SalesInvoice,
        total_paid: Decimal,
    ) -> None:
        """Update invoice status from current payment total."""
        if total_paid >= invoice.total_amount:
            await uow.sales_invoices.mark_status(invoice, InvoiceStatus.PAID)
        elif total_paid > ZERO_AMOUNT:
            await uow.sales_invoices.mark_status(
                invoice,
                InvoiceStatus.PARTIALLY_PAID,
            )
        else:
            await uow.sales_invoices.mark_status(invoice, InvoiceStatus.ISSUED)
