"""Application service for the canonical Sales workflow."""

import uuid
from collections.abc import Callable
from typing import Any, Protocol, cast

from app.common.events import EventDispatcher
from app.modules.catalog.models import CatalogItem, CatalogItemStatus
from app.modules.sales.canonical_schemas import (
    CanonicalInvoiceDraftRequest,
    CanonicalInvoiceDraftUpdate,
    CanonicalInvoiceLineRequest,
    CanonicalInvoiceResponse,
)
from app.modules.sales.domain import (
    InvoiceLifecycle,
    InvoiceLineValue,
)
from app.modules.sales.events import (
    InvoiceCancelledEvent,
    InvoiceCreatedEvent,
    InvoiceIssuedEvent,
    InvoiceUpdatedEvent,
)
from app.modules.sales.exceptions import (
    SalesCustomerNotFoundException,
    SalesInvoiceNotFoundException,
    SalesInvoiceValidationException,
)
from app.modules.sales.financial_rules import (
    CreditValidationHook,
    SalesFinancialRulesEngine,
    StoredFinancialInvoice,
)
from app.modules.sales.invoice_numbering import (
    InvoiceNumberService,
    InvoiceSequenceRepository,
)
from app.modules.sales.models import Customer, InvoiceStatus, SalesInvoice
from app.modules.sales.schemas import (
    InvoiceCreateRequest,
    InvoiceLineRequest,
    InvoiceUpdateRequest,
)


class CustomerReader(Protocol):
    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None: ...


class CatalogReader(Protocol):
    async def get_by_id(self, item_id: uuid.UUID) -> CatalogItem | None: ...


class BusinessReader(Protocol):
    async def get_settings(self, business_id: uuid.UUID) -> object | None: ...


class InvoiceRepository(Protocol):
    async def create(self, request: InvoiceCreateRequest) -> SalesInvoice: ...
    async def get_by_id(self, invoice_id: uuid.UUID) -> SalesInvoice | None: ...
    async def update(
        self, invoice: SalesInvoice, request: InvoiceUpdateRequest
    ) -> SalesInvoice: ...
    async def add_line(
        self, invoice: SalesInvoice, request: InvoiceLineRequest
    ) -> Any: ...
    async def remove_line(self, line: Any) -> None: ...
    async def mark_status(
        self, invoice: SalesInvoice, status: InvoiceStatus
    ) -> SalesInvoice: ...


class CanonicalSalesUnitOfWork(Protocol):
    businesses: BusinessReader
    customers: CustomerReader
    catalog_items: CatalogReader
    sales_invoices: InvoiceRepository
    invoice_number_sequences: InvoiceSequenceRepository

    async def __aenter__(self) -> "CanonicalSalesUnitOfWork": ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None: ...
    async def commit(self) -> None: ...


class SalesWorkflowHook(Protocol):
    async def before_validation(
        self, operation: str, invoice_id: uuid.UUID | None
    ) -> None: ...
    async def after_validation(
        self, operation: str, invoice_id: uuid.UUID | None
    ) -> None: ...
    async def before_transition(
        self, invoice: SalesInvoice, target: InvoiceStatus
    ) -> None: ...
    async def after_transition(
        self, invoice: SalesInvoice, target: InvoiceStatus
    ) -> None: ...


class CanonicalSalesInvoiceService:
    """Canonical workflow; deterministic and free of downstream side effects."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], CanonicalSalesUnitOfWork],
        event_dispatcher: EventDispatcher,
        *,
        number_service: InvoiceNumberService | None = None,
        hooks: tuple[SalesWorkflowHook, ...] = (),
        financial_rules: SalesFinancialRulesEngine | None = None,
        credit_hooks: tuple[CreditValidationHook, ...] = (),
    ) -> None:
        self._uow_factory = unit_of_work_factory
        self._events = event_dispatcher
        self._numbers = number_service or InvoiceNumberService()
        self._hooks = hooks
        self._financial = financial_rules or SalesFinancialRulesEngine()
        self._credit_hooks = credit_hooks
        self._lifecycle = InvoiceLifecycle()

    async def create_draft(
        self, request: CanonicalInvoiceDraftRequest
    ) -> CanonicalInvoiceResponse:
        await self._run("before_validation", "create", None)
        async with self._uow_factory() as uow:
            customer = await uow.customers.get_by_id(request.customer_id)
            if customer is None:
                raise SalesCustomerNotFoundException("Customer not found")
            if customer.business_id != request.business_id:
                raise SalesInvoiceValidationException(
                    "Customer does not belong to invoice business"
                )
            settings = await uow.businesses.get_settings(request.business_id)
            configured_currency = getattr(settings, "currency", "INR")
            currency = self._financial.validate_currency(
                request.currency, configured_currency
            )
            lines = await self._prepare_lines(uow, request.business_id, request.lines)
            totals = self._financial.calculate([value for _, value in lines])
            due_date = request.due_date
            if request.payment_terms_days is not None:
                due_date = self._financial.due_date(
                    request.invoice_date, request.payment_terms_days
                )
            self._financial.validate_due_date(request.invoice_date, due_date)
            for hook in self._credit_hooks:
                await hook.validate(
                    business_id=request.business_id,
                    customer_id=request.customer_id,
                    grand_total=totals.grand_total,
                    currency=currency,
                )
            number = await self._numbers.next_number(
                uow.invoice_number_sequences,
                business_id=request.business_id,
                invoice_date=request.invoice_date,
            )
            await self._run("after_validation", "create", None)
            legacy_lines = [line for line, _ in lines]
            invoice = await uow.sales_invoices.create(
                InvoiceCreateRequest(
                    business_id=request.business_id,
                    customer_id=request.customer_id,
                    invoice_number=number,
                    invoice_date=request.invoice_date,
                    due_date=due_date,
                    status=InvoiceStatus.DRAFT,
                    subtotal=totals.subtotal,
                    discount_amount=totals.discount_amount,
                    taxable_amount=totals.taxable_amount,
                    tax_amount=totals.tax.tax_amount + totals.tax.cess_amount,
                    total_amount=totals.grand_total,
                    notes=request.notes,
                    lines=legacy_lines,
                )
            )
            invoice.round_off = totals.round_off
            invoice.currency = currency
            invoice.payment_terms_days = request.payment_terms_days
            await uow.commit()
        await self._events.dispatch(
            InvoiceCreatedEvent(invoice.id, invoice.business_id)
        )
        return CanonicalInvoiceResponse.model_validate(invoice)

    async def issue(self, invoice_id: uuid.UUID) -> CanonicalInvoiceResponse:
        async with self._uow_factory() as uow:
            invoice = await self._invoice(uow, invoice_id)
            self._lifecycle.validate(invoice.status, InvoiceStatus.ISSUED)
            if not invoice.lines or any(
                line.catalog_item_id is None for line in invoice.lines
            ):
                raise SalesInvoiceValidationException(
                    "Canonical invoice lines must reference catalog items"
                )
            settings = await uow.businesses.get_settings(invoice.business_id)
            invoice.currency = self._financial.validate_currency(
                invoice.currency, getattr(settings, "currency", "INR")
            )
            for line in invoice.lines:
                if (
                    line.tax_rate > 0
                    and line.cgst_amount + line.sgst_amount + line.igst_amount == 0
                ):
                    components = self._financial.legacy_tax_components(line)
                    line.cgst_amount = components.cgst_amount
                    line.sgst_amount = components.sgst_amount
                    line.igst_amount = components.igst_amount
            self._financial.reconcile(cast(StoredFinancialInvoice, invoice))
            for hook in self._hooks:
                await hook.before_transition(invoice, InvoiceStatus.ISSUED)
            invoice = await uow.sales_invoices.mark_status(
                invoice, InvoiceStatus.ISSUED
            )
            await uow.commit()
        await self._events.dispatch(InvoiceIssuedEvent(invoice.id, invoice.business_id))
        for hook in self._hooks:
            await hook.after_transition(invoice, InvoiceStatus.ISSUED)
        return CanonicalInvoiceResponse.model_validate(invoice)

    async def get(self, invoice_id: uuid.UUID) -> CanonicalInvoiceResponse:
        async with self._uow_factory() as uow:
            invoice = await self._invoice(uow, invoice_id)
        if any(line.catalog_item_id is None for line in invoice.lines):
            raise SalesInvoiceValidationException(
                "Legacy invoice has not been migrated to the canonical workflow"
            )
        return CanonicalInvoiceResponse.model_validate(invoice)

    async def update_draft(
        self, invoice_id: uuid.UUID, request: CanonicalInvoiceDraftUpdate
    ) -> CanonicalInvoiceResponse:
        await self._run("before_validation", "update", invoice_id)
        async with self._uow_factory() as uow:
            invoice = await self._invoice(uow, invoice_id)
            self._lifecycle.ensure_editable(invoice.status)
            candidate_date = request.invoice_date or invoice.invoice_date
            candidate_due = (
                request.due_date
                if "due_date" in request.model_fields_set
                else invoice.due_date
            )
            update: dict[str, object] = {}
            for field in ("invoice_date", "due_date", "notes"):
                if field in request.model_fields_set:
                    update[field] = getattr(request, field)
            if request.lines is not None:
                lines = await self._prepare_lines(
                    uow, invoice.business_id, request.lines
                )
                totals = self._financial.calculate([value for _, value in lines])
                update.update(
                    subtotal=totals.subtotal,
                    discount_amount=totals.discount_amount,
                    taxable_amount=totals.taxable_amount,
                    tax_amount=totals.tax.tax_amount + totals.tax.cess_amount,
                    round_off=totals.round_off,
                    total_amount=totals.grand_total,
                )
                for old_line in list(invoice.lines):
                    await uow.sales_invoices.remove_line(old_line)
                invoice.lines = []
                for line, _ in lines:
                    invoice.lines.append(
                        await uow.sales_invoices.add_line(invoice, line)
                    )
            settings = await uow.businesses.get_settings(invoice.business_id)
            if request.currency is not None:
                invoice.currency = self._financial.validate_currency(
                    request.currency, getattr(settings, "currency", "INR")
                )
            if request.payment_terms_days is not None:
                candidate_due = self._financial.due_date(
                    candidate_date, request.payment_terms_days
                )
                update["due_date"] = candidate_due
                invoice.payment_terms_days = request.payment_terms_days
            self._financial.validate_due_date(candidate_date, candidate_due)
            invoice = await uow.sales_invoices.update(
                invoice, InvoiceUpdateRequest(**update)
            )
            await self._run("after_validation", "update", invoice_id)
            await uow.commit()
        await self._events.dispatch(
            InvoiceUpdatedEvent(invoice.id, invoice.business_id)
        )
        return CanonicalInvoiceResponse.model_validate(invoice)

    async def cancel(self, invoice_id: uuid.UUID) -> CanonicalInvoiceResponse:
        async with self._uow_factory() as uow:
            invoice = await self._invoice(uow, invoice_id)
            self._lifecycle.validate(invoice.status, InvoiceStatus.CANCELLED)
            invoice = await uow.sales_invoices.mark_status(
                invoice, InvoiceStatus.CANCELLED
            )
            await uow.commit()
        await self._events.dispatch(
            InvoiceCancelledEvent(invoice.id, invoice.business_id)
        )
        return CanonicalInvoiceResponse.model_validate(invoice)

    async def _prepare_lines(
        self,
        uow: CanonicalSalesUnitOfWork,
        business_id: uuid.UUID,
        requested: list[CanonicalInvoiceLineRequest],
    ) -> list[tuple[InvoiceLineRequest, InvoiceLineValue]]:
        prepared = []
        for line in requested:
            item = await uow.catalog_items.get_by_id(line.catalog_item_id)
            if (
                item is None
                or item.business_id != business_id
                or item.status != CatalogItemStatus.ACTIVE
            ):
                raise SalesInvoiceValidationException(
                    "Catalog item is unavailable for this business",
                    details={"catalog_item_id": str(line.catalog_item_id)},
                )
            value = InvoiceLineValue(
                line.quantity,
                line.unit_price,
                line.discount,
                item.gst_rate,
                item.cess_rate,
            )
            breakdown = self._financial.calculate_line(value)
            prepared.append(
                (
                    InvoiceLineRequest(
                        catalog_item_id=item.id,
                        description=item.name,
                        quantity=line.quantity,
                        unit_price=line.unit_price,
                        discount=line.discount,
                        tax_rate=item.gst_rate,
                        cgst_amount=breakdown.cgst_amount,
                        sgst_amount=breakdown.sgst_amount,
                        igst_amount=breakdown.igst_amount,
                        cess_amount=breakdown.cess_amount,
                        line_total=breakdown.line_total,
                    ),
                    value,
                )
            )
        return prepared

    async def _invoice(
        self, uow: CanonicalSalesUnitOfWork, invoice_id: uuid.UUID
    ) -> SalesInvoice:
        invoice = await uow.sales_invoices.get_by_id(invoice_id)
        if invoice is None:
            raise SalesInvoiceNotFoundException("Invoice not found")
        return invoice

    async def _run(
        self, name: str, operation: str, invoice_id: uuid.UUID | None
    ) -> None:
        for hook in self._hooks:
            await getattr(hook, name)(operation, invoice_id)
