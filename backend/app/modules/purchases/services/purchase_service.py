"""Purchase invoice service."""

import uuid
from collections.abc import Callable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from app.common.events import EventDispatcher
from app.common.pagination import Page, PaginationParams
from app.modules.purchases.events import (
    PurchaseApprovedEvent,
    PurchaseCancelledEvent,
    PurchaseCreatedEvent,
    PurchasePaidEvent,
    PurchaseReceivedEvent,
    PurchaseUpdatedEvent,
)
from app.modules.purchases.exceptions import (
    DuplicatePurchaseInvoiceException,
    DuplicatePurchaseNumberException,
    InvalidPurchaseStatusException,
    PurchaseNotFoundException,
    PurchaseValidationException,
    SupplierInactiveException,
    SupplierNotFoundException,
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
    PurchaseInvoiceResponse,
    PurchaseInvoiceUpdate,
)

MONEY_PLACES = Decimal("0.01")
TAX_PERCENT_DIVISOR = Decimal("100.00")
PURCHASE_NUMBER_ATTEMPTS = 10


class PurchaseSupplierRepository(Protocol):
    """Supplier repository behavior required by purchase service."""

    async def get_by_id(self, supplier_id: uuid.UUID) -> Supplier | None:
        """Return a supplier by UUID."""
        ...


class PurchasePersistenceRepository(Protocol):
    """Purchase repository behavior required by purchase service."""

    async def create(
        self,
        request: PurchaseInvoiceCreate,
        *,
        business_id: uuid.UUID,
        purchase_number: str,
    ) -> PurchaseInvoice:
        """Create a purchase invoice."""
        ...

    async def get_by_id(self, purchase_id: uuid.UUID) -> PurchaseInvoice | None:
        """Return a purchase invoice by UUID."""
        ...

    async def get_by_purchase_number(
        self,
        *,
        business_id: uuid.UUID,
        purchase_number: str,
    ) -> PurchaseInvoice | None:
        """Return a purchase invoice by purchase number."""
        ...

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
        """Return purchase invoices for a business."""
        ...

    async def search(
        self,
        *,
        business_id: uuid.UUID,
        query: str,
        pagination: PaginationParams | None = None,
    ) -> Page[PurchaseInvoice]:
        """Search purchase invoices for a business."""
        ...

    async def update(
        self,
        purchase_invoice: PurchaseInvoice,
        request: PurchaseInvoiceUpdate,
    ) -> PurchaseInvoice:
        """Update a purchase invoice."""
        ...


class PurchaseLinePersistenceRepository(Protocol):
    """Purchase line repository behavior required by purchase service."""

    async def create(
        self,
        request: PurchaseInvoiceLineCreate,
        *,
        purchase_invoice_id: uuid.UUID,
    ) -> PurchaseInvoiceLine:
        """Create a purchase invoice line."""
        ...

    async def delete(self, line: PurchaseInvoiceLine) -> None:
        """Soft-delete a purchase invoice line."""
        ...


class PurchaseUnitOfWork(Protocol):
    """Unit of Work contract required by purchase service."""

    suppliers: PurchaseSupplierRepository
    purchase_invoices: PurchasePersistenceRepository
    purchase_invoice_lines: PurchaseLinePersistenceRepository

    async def __aenter__(self) -> "PurchaseUnitOfWork":
        """Enter the purchase transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit the purchase transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit purchase changes."""
        ...


UnitOfWorkFactory = Callable[[], PurchaseUnitOfWork]


class PurchaseAccountingKernel(Protocol):
    """Accounting kernel behavior required by purchase workflows."""

    async def record_purchase_invoice(self, purchase_id: uuid.UUID) -> object:
        """Post an approved purchase invoice to accounting."""
        ...

    async def record_supplier_payment(self, purchase_id: uuid.UUID) -> object:
        """Post a paid purchase invoice payment to accounting."""
        ...


class PurchaseService:
    """Coordinate purchase invoice lifecycle operations."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
        accounting_kernel: PurchaseAccountingKernel | None = None,
    ) -> None:
        """Initialize service dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._accounting_kernel = accounting_kernel

    async def create_purchase(
        self,
        request: PurchaseInvoiceCreate,
        *,
        business_id: uuid.UUID,
    ) -> PurchaseInvoiceResponse:
        """Create a draft purchase invoice and publish an event."""
        validated_request = PurchaseInvoiceCreate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            await self._validate_supplier(
                uow,
                validated_request.supplier_id,
                business_id,
            )
            await self._ensure_unique_invoice_number(
                uow,
                business_id=business_id,
                supplier_id=validated_request.supplier_id,
                invoice_number=validated_request.invoice_number,
            )
            purchase_number = await self._generate_unique_purchase_number(
                uow,
                business_id,
                validated_request.invoice_date,
            )
            prepared_request = self._prepare_create_request(validated_request)
            purchase_invoice = await uow.purchase_invoices.create(
                prepared_request,
                business_id=business_id,
                purchase_number=purchase_number,
            )
            await self._event_dispatcher.dispatch(
                PurchaseCreatedEvent(
                    purchase_id=purchase_invoice.id,
                    business_id=purchase_invoice.business_id,
                )
            )
            await uow.commit()
        return PurchaseInvoiceResponse.model_validate(purchase_invoice)

    async def update_purchase(
        self,
        purchase_id: uuid.UUID,
        request: PurchaseInvoiceUpdate,
    ) -> PurchaseInvoiceResponse:
        """Update a draft purchase invoice and publish an event."""
        validated_request = PurchaseInvoiceUpdate.model_validate(request)
        async with self._unit_of_work_factory() as uow:
            purchase_invoice = await self._get_existing_purchase(uow, purchase_id)
            self._ensure_editable(purchase_invoice)
            self._ensure_no_direct_status_update(validated_request)
            supplier_id = validated_request.supplier_id or purchase_invoice.supplier_id
            await self._validate_supplier(
                uow,
                supplier_id,
                purchase_invoice.business_id,
            )
            invoice_number = (
                validated_request.invoice_number or purchase_invoice.invoice_number
            )
            await self._ensure_unique_invoice_number(
                uow,
                business_id=purchase_invoice.business_id,
                supplier_id=supplier_id,
                invoice_number=invoice_number,
                current_purchase_id=purchase_invoice.id,
            )
            prepared_request = self._prepare_update_request(
                purchase_invoice,
                validated_request,
            )
            purchase_invoice = await uow.purchase_invoices.update(
                purchase_invoice,
                prepared_request,
            )
            if prepared_request.lines is not None:
                for line in list(purchase_invoice.lines):
                    await uow.purchase_invoice_lines.delete(line)
                purchase_invoice.lines = []
                for line_request in self._line_updates_to_create_requests(
                    prepared_request
                ):
                    line = await uow.purchase_invoice_lines.create(
                        line_request,
                        purchase_invoice_id=purchase_invoice.id,
                    )
                    purchase_invoice.lines.append(line)
            await self._event_dispatcher.dispatch(
                PurchaseUpdatedEvent(
                    purchase_id=purchase_invoice.id,
                    business_id=purchase_invoice.business_id,
                )
            )
            await uow.commit()
        return PurchaseInvoiceResponse.model_validate(purchase_invoice)

    async def approve_purchase(self, purchase_id: uuid.UUID) -> PurchaseInvoiceResponse:
        """Approve a draft purchase invoice."""
        response = await self._transition_purchase(
            purchase_id,
            target_status=PurchaseStatus.APPROVED,
            allowed_statuses={PurchaseStatus.DRAFT},
            event_name="approved",
        )
        if self._accounting_kernel is not None:
            await self._accounting_kernel.record_purchase_invoice(purchase_id)
        return response

    async def mark_received(self, purchase_id: uuid.UUID) -> PurchaseInvoiceResponse:
        """Mark an approved purchase invoice as received."""
        return await self._transition_purchase(
            purchase_id,
            target_status=PurchaseStatus.RECEIVED,
            allowed_statuses={PurchaseStatus.APPROVED},
            event_name="received",
        )

    async def mark_paid(self, purchase_id: uuid.UUID) -> PurchaseInvoiceResponse:
        """Mark a received purchase invoice as paid."""
        response = await self._transition_purchase(
            purchase_id,
            target_status=PurchaseStatus.PAID,
            allowed_statuses={PurchaseStatus.RECEIVED},
            event_name="paid",
        )
        if self._accounting_kernel is not None:
            await self._accounting_kernel.record_supplier_payment(purchase_id)
        return response

    async def cancel_purchase(self, purchase_id: uuid.UUID) -> PurchaseInvoiceResponse:
        """Cancel a purchase invoice before payment."""
        return await self._transition_purchase(
            purchase_id,
            target_status=PurchaseStatus.CANCELLED,
            allowed_statuses={
                PurchaseStatus.DRAFT,
                PurchaseStatus.APPROVED,
                PurchaseStatus.RECEIVED,
            },
            event_name="cancelled",
        )

    async def get_purchase(self, purchase_id: uuid.UUID) -> PurchaseInvoiceResponse:
        """Return a purchase invoice by UUID."""
        async with self._unit_of_work_factory() as uow:
            purchase_invoice = await self._get_existing_purchase(uow, purchase_id)
            await uow.commit()
        return PurchaseInvoiceResponse.model_validate(purchase_invoice)

    async def list_purchases(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        sort: str | None = None,
        supplier_id: uuid.UUID | None = None,
        status: PurchaseStatus | None = None,
        invoice_date_from: date | None = None,
        invoice_date_to: date | None = None,
        due_date_from: date | None = None,
        due_date_to: date | None = None,
        purchase_number: str | None = None,
        invoice_number: str | None = None,
        search: str | None = None,
    ) -> Page[PurchaseInvoiceResponse]:
        """Return paginated purchase invoices for a business."""
        async with self._unit_of_work_factory() as uow:
            if search:
                page = await uow.purchase_invoices.search(
                    business_id=business_id,
                    query=search,
                    pagination=pagination,
                )
            else:
                page = await uow.purchase_invoices.list(
                    business_id=business_id,
                    pagination=pagination,
                    sort=sort,
                    supplier_id=supplier_id,
                    status=status,
                    invoice_date_from=invoice_date_from,
                    invoice_date_to=invoice_date_to,
                    due_date_from=due_date_from,
                    due_date_to=due_date_to,
                    purchase_number=purchase_number,
                    invoice_number=invoice_number,
                )
            await uow.commit()
        return Page.create(
            items=[
                PurchaseInvoiceResponse.model_validate(purchase)
                for purchase in page.items
            ],
            total=page.meta.total,
            params=pagination or PaginationParams(),
        )

    async def _transition_purchase(
        self,
        purchase_id: uuid.UUID,
        *,
        target_status: PurchaseStatus,
        allowed_statuses: set[PurchaseStatus],
        event_name: str,
    ) -> PurchaseInvoiceResponse:
        """Apply a purchase lifecycle status transition."""
        async with self._unit_of_work_factory() as uow:
            purchase_invoice = await self._get_existing_purchase(uow, purchase_id)
            if purchase_invoice.status not in allowed_statuses:
                raise InvalidPurchaseStatusException(
                    "Purchase status transition is not allowed",
                    details={
                        "purchase_id": str(purchase_id),
                        "status": purchase_invoice.status.value,
                        "target_status": target_status.value,
                    },
                )
            purchase_invoice = await uow.purchase_invoices.update(
                purchase_invoice,
                PurchaseInvoiceUpdate(status=target_status),
            )
            await self._dispatch_status_event(purchase_invoice, event_name)
            await uow.commit()
        return PurchaseInvoiceResponse.model_validate(purchase_invoice)

    async def _get_existing_purchase(
        self,
        uow: PurchaseUnitOfWork,
        purchase_id: uuid.UUID,
    ) -> PurchaseInvoice:
        """Return a purchase invoice or raise not found."""
        purchase_invoice = await uow.purchase_invoices.get_by_id(purchase_id)
        if purchase_invoice is None:
            raise PurchaseNotFoundException(
                "Purchase invoice not found",
                details={"purchase_id": str(purchase_id)},
            )
        return purchase_invoice

    async def _validate_supplier(
        self,
        uow: PurchaseUnitOfWork,
        supplier_id: uuid.UUID,
        business_id: uuid.UUID,
    ) -> Supplier:
        """Validate supplier belongs to the business and is active."""
        supplier = await uow.suppliers.get_by_id(supplier_id)
        if supplier is None:
            raise SupplierNotFoundException(
                "Supplier not found",
                details={"supplier_id": str(supplier_id)},
            )
        if supplier.business_id != business_id:
            raise PurchaseValidationException(
                "Supplier does not belong to purchase business",
                details={
                    "business_id": str(business_id),
                    "supplier_id": str(supplier_id),
                },
            )
        if not supplier.is_active:
            raise SupplierInactiveException(
                "Inactive suppliers cannot be used for purchases",
                details={"supplier_id": str(supplier_id)},
            )
        return supplier

    async def _ensure_unique_invoice_number(
        self,
        uow: PurchaseUnitOfWork,
        *,
        business_id: uuid.UUID,
        supplier_id: uuid.UUID,
        invoice_number: str,
        current_purchase_id: uuid.UUID | None = None,
    ) -> None:
        """Validate supplier invoice number uniqueness within a supplier."""
        page = await uow.purchase_invoices.list(
            business_id=business_id,
            supplier_id=supplier_id,
            invoice_number=invoice_number,
            pagination=PaginationParams(page=1, size=100),
        )
        if any(purchase.id != current_purchase_id for purchase in page.items):
            raise DuplicatePurchaseInvoiceException(
                "Invoice number already exists for this supplier",
                details={
                    "business_id": str(business_id),
                    "supplier_id": str(supplier_id),
                    "invoice_number": invoice_number,
                },
            )

    async def _generate_unique_purchase_number(
        self,
        uow: PurchaseUnitOfWork,
        business_id: uuid.UUID,
        invoice_date: date,
    ) -> str:
        """Generate a unique business-scoped purchase number."""
        for _attempt in range(PURCHASE_NUMBER_ATTEMPTS):
            purchase_number = (
                f"PUR-{invoice_date:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
            )
            existing = await uow.purchase_invoices.get_by_purchase_number(
                business_id=business_id,
                purchase_number=purchase_number,
            )
            if existing is None:
                return purchase_number
        raise DuplicatePurchaseNumberException(
            "Unable to generate a unique purchase number",
            details={"business_id": str(business_id)},
        )

    def _ensure_editable(self, purchase_invoice: PurchaseInvoice) -> None:
        """Raise when a purchase invoice cannot be edited."""
        if purchase_invoice.status != PurchaseStatus.DRAFT:
            raise InvalidPurchaseStatusException(
                "Only draft purchase invoices may be edited",
                details={
                    "purchase_id": str(purchase_invoice.id),
                    "status": purchase_invoice.status.value,
                },
            )

    def _ensure_no_direct_status_update(self, request: PurchaseInvoiceUpdate) -> None:
        """Prevent general updates from bypassing lifecycle workflow methods."""
        if request.status is not None:
            raise InvalidPurchaseStatusException(
                "Use workflow methods to change purchase status",
                details={"status": request.status.value},
            )

    def _prepare_create_request(
        self,
        request: PurchaseInvoiceCreate,
    ) -> PurchaseInvoiceCreate:
        """Calculate purchase totals before persistence."""
        totals = self._calculate_totals(request.lines)
        return request.model_copy(update={"status": PurchaseStatus.DRAFT, **totals})

    def _prepare_update_request(
        self,
        purchase_invoice: PurchaseInvoice,
        request: PurchaseInvoiceUpdate,
    ) -> PurchaseInvoiceUpdate:
        """Calculate purchase update totals when lines are supplied."""
        _ = purchase_invoice
        if request.lines is None:
            return request
        line_requests = self._line_updates_to_create_requests(request)
        totals = self._calculate_totals(line_requests)
        return request.model_copy(update=totals)

    def _line_updates_to_create_requests(
        self,
        request: PurchaseInvoiceUpdate,
    ) -> list[PurchaseInvoiceLineCreate]:
        """Convert full line update payloads to create payloads."""
        if request.lines is None:
            return []
        line_requests: list[PurchaseInvoiceLineCreate] = []
        for line in request.lines:
            if (
                line.description is None
                or line.quantity is None
                or line.unit_cost is None
            ):
                raise PurchaseValidationException(
                    "Updated purchase lines must include description, "
                    "quantity, and unit_cost"
                )
            line_requests.append(
                PurchaseInvoiceLineCreate(
                    description=line.description,
                    quantity=line.quantity,
                    unit_cost=line.unit_cost,
                    tax_rate=line.tax_rate or Decimal("0.00"),
                    line_total=line.line_total or Decimal("0.00"),
                )
            )
        return line_requests

    def _calculate_totals(
        self,
        lines: list[PurchaseInvoiceLineCreate],
    ) -> dict[str, Decimal | list[PurchaseInvoiceLineCreate]]:
        """Calculate purchase line totals and aggregate totals."""
        if not lines:
            raise PurchaseValidationException(
                "Purchase invoice must include at least one line"
            )

        prepared_lines: list[PurchaseInvoiceLineCreate] = []
        subtotal = Decimal("0.00")
        tax_amount = Decimal("0.00")
        for line in lines:
            line_subtotal = self._money(line.quantity * line.unit_cost)
            line_tax = self._money(line_subtotal * line.tax_rate / TAX_PERCENT_DIVISOR)
            line_total = self._money(line_subtotal + line_tax)
            prepared_lines.append(line.model_copy(update={"line_total": line_total}))
            subtotal += line_subtotal
            tax_amount += line_tax

        subtotal = self._money(subtotal)
        tax_amount = self._money(tax_amount)
        return {
            "lines": prepared_lines,
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "total_amount": self._money(subtotal + tax_amount),
        }

    async def _dispatch_status_event(
        self,
        purchase_invoice: PurchaseInvoice,
        event_name: str,
    ) -> None:
        """Publish a purchase status event."""
        events = {
            "approved": PurchaseApprovedEvent,
            "received": PurchaseReceivedEvent,
            "paid": PurchasePaidEvent,
            "cancelled": PurchaseCancelledEvent,
        }
        event_type = events[event_name]
        await self._event_dispatcher.dispatch(
            event_type(
                purchase_id=purchase_invoice.id,
                business_id=purchase_invoice.business_id,
            )
        )

    def _money(self, value: Decimal) -> Decimal:
        """Round monetary values to two decimal places."""
        return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)
