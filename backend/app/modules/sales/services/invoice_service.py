"""Sales invoice service."""

import uuid
from collections.abc import Callable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from app.common.events import EventDispatcher
from app.modules.sales.events import (
    InvoiceCancelledEvent,
    InvoiceCreatedEvent,
    InvoiceIssuedEvent,
    InvoicePaidEvent,
    InvoicePartiallyPaidEvent,
    InvoiceUpdatedEvent,
)
from app.modules.sales.exceptions import (
    SalesCustomerNotFoundException,
    SalesDuplicateInvoiceNumberException,
    SalesInvalidInvoiceStatusException,
    SalesInvoiceNotFoundException,
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
    InvoiceResponse,
    InvoiceUpdateRequest,
)

MONEY_PLACES = Decimal("0.01")
TAX_PERCENT_DIVISOR = Decimal("100.00")


class SalesCustomerRepository(Protocol):
    """Customer repository behavior required by invoice service."""

    async def create(self, request: CustomerCreateRequest) -> Customer:
        """Create a customer."""
        ...

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        """Return a customer by UUID."""
        ...


class SalesInvoiceLifecycleRepository(Protocol):
    """Invoice repository behavior required by invoice service."""

    async def create(self, request: InvoiceCreateRequest) -> SalesInvoice:
        """Create an invoice."""
        ...

    async def update(
        self,
        invoice: SalesInvoice,
        request: InvoiceUpdateRequest,
    ) -> SalesInvoice:
        """Update an invoice."""
        ...

    async def get_by_id(self, invoice_id: uuid.UUID) -> SalesInvoice | None:
        """Return an invoice by UUID."""
        ...

    async def get_by_invoice_number(
        self,
        *,
        business_id: uuid.UUID,
        invoice_number: str,
    ) -> SalesInvoice | None:
        """Return an invoice by business-scoped invoice number."""
        ...

    async def add_line(
        self,
        invoice: SalesInvoice,
        request: InvoiceLineRequest,
    ) -> SalesInvoiceLine:
        """Add an invoice line."""
        ...

    async def remove_line(self, line: SalesInvoiceLine) -> None:
        """Remove an invoice line."""
        ...

    async def mark_status(
        self,
        invoice: SalesInvoice,
        status: InvoiceStatus,
    ) -> SalesInvoice:
        """Mark invoice status."""
        ...


class SalesInvoiceUnitOfWork(Protocol):
    """Unit of Work contract required by invoice service."""

    customers: SalesCustomerRepository
    sales_invoices: SalesInvoiceLifecycleRepository

    async def __aenter__(self) -> "SalesInvoiceUnitOfWork":
        """Enter the invoice transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the invoice transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit invoice changes."""
        ...


UnitOfWorkFactory = Callable[[], SalesInvoiceUnitOfWork]


class SalesAccountingKernel(Protocol):
    """Accounting integration behavior required by invoice service."""

    async def record_sales_invoice(self, invoice_id: uuid.UUID) -> object:
        """Post a sales invoice to accounting."""
        ...


class SalesInvoiceService:
    """Coordinate sales invoice lifecycle operations."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
        accounting_kernel: SalesAccountingKernel | None = None,
    ) -> None:
        """Initialize service dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._accounting_kernel = accounting_kernel

    async def create_invoice(
        self,
        request: InvoiceCreateRequest,
        *,
        customer_request: CustomerCreateRequest | None = None,
    ) -> InvoiceResponse:
        """Create a sales invoice and publish an event."""
        validated_request = self._prepare_create_request(
            InvoiceCreateRequest.model_validate(request)
        )

        async with self._unit_of_work_factory() as uow:
            customer = await self._get_or_create_customer(
                uow,
                validated_request.customer_id,
                customer_request,
            )
            if customer.business_id != validated_request.business_id:
                raise SalesInvoiceValidationException(
                    "Customer does not belong to invoice business",
                    details={
                        "business_id": str(validated_request.business_id),
                        "customer_id": str(customer.id),
                    },
                )
            if customer.id != validated_request.customer_id:
                validated_request = validated_request.model_copy(
                    update={"customer_id": customer.id}
                )

            await self._ensure_invoice_number_available(
                uow,
                business_id=validated_request.business_id,
                invoice_number=validated_request.invoice_number,
            )
            invoice = await uow.sales_invoices.create(validated_request)
            await self._event_dispatcher.dispatch(
                InvoiceCreatedEvent(
                    invoice_id=invoice.id,
                    business_id=invoice.business_id,
                )
            )
            await uow.commit()

        return InvoiceResponse.model_validate(invoice)

    async def update_invoice(
        self,
        invoice_id: uuid.UUID,
        request: InvoiceUpdateRequest,
    ) -> InvoiceResponse:
        """Update a sales invoice and publish an event."""
        validated_request = InvoiceUpdateRequest.model_validate(request)

        async with self._unit_of_work_factory() as uow:
            invoice = await self._get_existing_invoice(uow, invoice_id)
            self._ensure_editable(invoice)
            if (
                validated_request.invoice_number is not None
                and validated_request.invoice_number != invoice.invoice_number
            ):
                await self._ensure_invoice_number_available(
                    uow,
                    business_id=invoice.business_id,
                    invoice_number=validated_request.invoice_number,
                )

            prepared_request = self._prepare_update_request(validated_request)
            invoice = await uow.sales_invoices.update(invoice, prepared_request)
            if prepared_request.lines is not None:
                for line in list(invoice.lines):
                    await uow.sales_invoices.remove_line(line)
                invoice.lines = []
                for line_request in prepared_request.lines:
                    line = await uow.sales_invoices.add_line(invoice, line_request)
                    invoice.lines.append(line)

            await self._event_dispatcher.dispatch(
                InvoiceUpdatedEvent(
                    invoice_id=invoice.id,
                    business_id=invoice.business_id,
                )
            )
            await uow.commit()

        return InvoiceResponse.model_validate(invoice)

    async def issue_invoice(self, invoice_id: uuid.UUID) -> InvoiceResponse:
        """Issue a draft invoice."""
        response = await self._transition_invoice(
            invoice_id,
            target_status=InvoiceStatus.ISSUED,
            allowed_statuses={InvoiceStatus.DRAFT},
            event_name="issued",
        )
        if self._accounting_kernel is not None:
            await self._accounting_kernel.record_sales_invoice(invoice_id)
        return response

    async def cancel_invoice(self, invoice_id: uuid.UUID) -> InvoiceResponse:
        """Cancel an invoice."""
        return await self._transition_invoice(
            invoice_id,
            target_status=InvoiceStatus.CANCELLED,
            allowed_statuses={
                InvoiceStatus.DRAFT,
                InvoiceStatus.ISSUED,
                InvoiceStatus.PARTIALLY_PAID,
            },
            event_name="cancelled",
        )

    async def mark_partially_paid(self, invoice_id: uuid.UUID) -> InvoiceResponse:
        """Mark an issued invoice partially paid."""
        return await self._transition_invoice(
            invoice_id,
            target_status=InvoiceStatus.PARTIALLY_PAID,
            allowed_statuses={InvoiceStatus.ISSUED},
            event_name="partially_paid",
        )

    async def mark_paid(self, invoice_id: uuid.UUID) -> InvoiceResponse:
        """Mark an issued or partially paid invoice paid."""
        return await self._transition_invoice(
            invoice_id,
            target_status=InvoiceStatus.PAID,
            allowed_statuses={InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID},
            event_name="paid",
        )

    async def _transition_invoice(
        self,
        invoice_id: uuid.UUID,
        *,
        target_status: InvoiceStatus,
        allowed_statuses: set[InvoiceStatus],
        event_name: str,
    ) -> InvoiceResponse:
        """Apply an invoice lifecycle status transition."""
        async with self._unit_of_work_factory() as uow:
            invoice = await self._get_existing_invoice(uow, invoice_id)
            if invoice.status not in allowed_statuses:
                raise SalesInvalidInvoiceStatusException(
                    "Invoice status transition is not allowed",
                    details={
                        "invoice_id": str(invoice_id),
                        "status": invoice.status.value,
                        "target_status": target_status.value,
                    },
                )

            invoice = await uow.sales_invoices.mark_status(invoice, target_status)
            await self._dispatch_status_event(invoice, event_name)
            await uow.commit()

        return InvoiceResponse.model_validate(invoice)

    async def _get_or_create_customer(
        self,
        uow: SalesInvoiceUnitOfWork,
        customer_id: uuid.UUID,
        customer_request: CustomerCreateRequest | None,
    ) -> Customer:
        """Return existing customer or create one when request data is supplied."""
        customer = await uow.customers.get_by_id(customer_id)
        if customer is not None:
            return customer
        if customer_request is None:
            raise SalesCustomerNotFoundException(
                "Customer not found",
                details={"customer_id": str(customer_id)},
            )
        return await uow.customers.create(customer_request)

    async def _get_existing_invoice(
        self,
        uow: SalesInvoiceUnitOfWork,
        invoice_id: uuid.UUID,
    ) -> SalesInvoice:
        """Return existing invoice or raise a domain error."""
        invoice = await uow.sales_invoices.get_by_id(invoice_id)
        if invoice is None:
            raise SalesInvoiceNotFoundException(
                "Invoice not found",
                details={"invoice_id": str(invoice_id)},
            )
        return invoice

    async def _ensure_invoice_number_available(
        self,
        uow: SalesInvoiceUnitOfWork,
        *,
        business_id: uuid.UUID,
        invoice_number: str,
    ) -> None:
        """Raise when an invoice number already exists for a business."""
        existing = await uow.sales_invoices.get_by_invoice_number(
            business_id=business_id,
            invoice_number=invoice_number,
        )
        if existing is not None:
            raise SalesDuplicateInvoiceNumberException(
                "Invoice number already exists",
                details={
                    "business_id": str(business_id),
                    "invoice_number": invoice_number,
                },
            )

    def _prepare_create_request(
        self,
        request: InvoiceCreateRequest,
    ) -> InvoiceCreateRequest:
        """Calculate invoice totals before persistence."""
        invoice_number = request.invoice_number or self._generate_invoice_number(
            request.invoice_date
        )
        totals = self._calculate_totals(request.lines)
        return request.model_copy(
            update={
                "invoice_number": invoice_number,
                "status": InvoiceStatus.DRAFT,
                **totals,
            }
        )

    def _prepare_update_request(
        self,
        request: InvoiceUpdateRequest,
    ) -> InvoiceUpdateRequest:
        """Calculate invoice update totals when lines are supplied."""
        if request.lines is None:
            return request
        totals = self._calculate_totals(request.lines)
        return request.model_copy(update=totals)

    def _calculate_totals(
        self,
        lines: list[InvoiceLineRequest],
    ) -> dict[str, Decimal | list[InvoiceLineRequest]]:
        """Calculate invoice line totals and aggregate totals."""
        if not lines:
            raise SalesInvoiceValidationException(
                "Invoice must include at least one line"
            )

        prepared_lines: list[InvoiceLineRequest] = []
        subtotal = Decimal("0.00")
        discount_amount = Decimal("0.00")
        tax_amount = Decimal("0.00")

        for line in lines:
            gross = self._money(line.quantity * line.unit_price)
            discount = self._money(line.discount)
            if discount > gross:
                raise SalesInvoiceValidationException(
                    "Line discount cannot exceed line gross amount"
                )
            taxable_line_amount = self._money(gross - discount)
            line_tax = self._money(
                taxable_line_amount * line.tax_rate / TAX_PERCENT_DIVISOR
            )
            line_total = self._money(taxable_line_amount + line_tax)
            prepared_lines.append(line.model_copy(update={"line_total": line_total}))
            subtotal += gross
            discount_amount += discount
            tax_amount += line_tax

        taxable_amount = self._money(subtotal - discount_amount)
        total_amount = self._money(taxable_amount + tax_amount)
        return {
            "lines": prepared_lines,
            "subtotal": self._money(subtotal),
            "discount_amount": self._money(discount_amount),
            "taxable_amount": taxable_amount,
            "tax_amount": self._money(tax_amount),
            "total_amount": total_amount,
        }

    def _ensure_editable(self, invoice: SalesInvoice) -> None:
        """Raise when an invoice cannot be edited."""
        if invoice.status in {InvoiceStatus.PAID, InvoiceStatus.CANCELLED}:
            raise SalesInvalidInvoiceStatusException(
                "Invoice cannot be edited in its current status",
                details={
                    "invoice_id": str(invoice.id),
                    "status": invoice.status.value,
                },
            )

    async def _dispatch_status_event(
        self,
        invoice: SalesInvoice,
        event_name: str,
    ) -> None:
        """Publish an invoice status event."""
        events = {
            "issued": InvoiceIssuedEvent,
            "cancelled": InvoiceCancelledEvent,
            "partially_paid": InvoicePartiallyPaidEvent,
            "paid": InvoicePaidEvent,
        }
        event_type = events[event_name]
        await self._event_dispatcher.dispatch(
            event_type(invoice_id=invoice.id, business_id=invoice.business_id)
        )

    def _generate_invoice_number(self, invoice_date: date) -> str:
        """Generate a business-friendly invoice number."""
        return f"INV-{invoice_date:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"

    def _money(self, value: Decimal) -> Decimal:
        """Round monetary values to two decimal places."""
        return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
