"""Sales invoice service."""

import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Protocol

from app.common.events import EventDispatcher
from app.common.unit_of_work import supports_uow
from app.modules.gst.jurisdictions import (
    is_utgst_jurisdiction,
    validate_state_code,
)
from app.modules.gst.services import (
    GSTCalculationLineInput,
    GSTCalculationService,
    GSTSupplyType,
)
from app.modules.gst.services.pos_resolution_service import (
    PlaceOfSupplyResolutionService,
    SupplyResolutionContext,
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
    gstin_verifications: Any | None = None

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

    async def record_sales_invoice(
        self,
        invoice_id: uuid.UUID,
        uow: Any | None = None,
    ) -> object:
        """Post a sales invoice to accounting."""
        ...


class SalesStockEngine(Protocol):
    """Inventory integration behavior required by invoice service."""

    async def issue_sale(
        self,
        sales_invoice: SalesInvoice,
        *,
        warehouse_id: uuid.UUID | None = None,
        uow: Any | None = None,
    ) -> object:
        """Issue invoice stock movements."""
        ...

    async def issue_sale_lines(
        self,
        sales_invoice: SalesInvoice,
        lines: list[Any],
        *,
        uow: Any | None = None,
    ) -> object:
        """Issue specific pre-resolved stock lines."""
        ...


class SalesInvoiceService:
    """Coordinate sales invoice lifecycle operations."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
        accounting_kernel: SalesAccountingKernel | None = None,
        stock_engine: SalesStockEngine | None = None,
        gst_calculation_service: GSTCalculationService | None = None,
        pos_resolution_service: PlaceOfSupplyResolutionService | None = None,
        default_supplier_state_code: str = "29",
    ) -> None:
        """Initialize service dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._accounting_kernel = accounting_kernel
        self._stock_engine = stock_engine
        self._gst_calculation_service = (
            gst_calculation_service or GSTCalculationService(event_dispatcher)
        )
        self._pos_resolution_service = (
            pos_resolution_service or PlaceOfSupplyResolutionService()
        )
        self._default_supplier_state_code = default_supplier_state_code

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
            await uow.commit()
            await self._event_dispatcher.dispatch(
                InvoiceCreatedEvent(
                    invoice_id=invoice.id,
                    business_id=invoice.business_id,
                )
            )
            reloaded = await uow.sales_invoices.get_by_id(invoice.id)
            return InvoiceResponse.model_validate(reloaded or invoice)

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

            await uow.commit()
            await self._event_dispatcher.dispatch(
                InvoiceUpdatedEvent(
                    invoice_id=invoice.id,
                    business_id=invoice.business_id,
                )
            )
            reloaded = await uow.sales_invoices.get_by_id(invoice.id)
            return InvoiceResponse.model_validate(reloaded or invoice)

    async def issue_invoice(
        self,
        invoice_id: uuid.UUID,
        *,
        resolution_context: SupplyResolutionContext | None = None,
    ) -> InvoiceResponse:
        """Issue a draft invoice within a unified financial transaction boundary.

        Deterministically resolves place of supply and persists immutable tax snapshot.
        """
        async with self._unit_of_work_factory() as uow:
            invoice = await self._get_existing_invoice(uow, invoice_id)
            if invoice.status != InvoiceStatus.DRAFT:
                raise SalesInvalidInvoiceStatusException(
                    "Invoice status transition is not allowed",
                    details={
                        "invoice_id": str(invoice_id),
                        "status": invoice.status.value,
                        "target_status": InvoiceStatus.ISSUED.value,
                    },
                )

            customer = None
            if hasattr(uow, "customers") and uow.customers is not None:
                customer = await uow.customers.get_by_id(invoice.customer_id)
            if customer is None:
                customer = getattr(invoice, "customer", None)
            supplier_state = await self._resolve_supplier_state_code(
                uow, invoice.business_id
            )

            # Determine Place of Supply & Tax Classification
            if resolution_context is not None:
                if (
                    resolution_context.is_bill_to_ship_to
                    and resolution_context.buyer_evidence is None
                    and getattr(uow, "gstin_verifications", None) is not None
                    and resolution_context.buyer_gstin
                ):
                    stored_record = await uow.gstin_verifications.get_by_gstin(
                        resolution_context.buyer_gstin,
                        business_id=invoice.business_id,
                    )
                    if stored_record is not None:
                        resolution_context = replace(
                            resolution_context,
                            buyer_evidence=stored_record.to_evidence_record(),
                        )

                res = self._pos_resolution_service.resolve_supply(resolution_context)
                pos = res.place_of_supply
                is_intra = res.is_intra_state
                is_ut = res.is_utgst
            elif invoice.place_of_supply is not None:
                pos = validate_state_code(invoice.place_of_supply)
                if pos == supplier_state:
                    is_intra = True
                    is_ut = is_utgst_jurisdiction(pos)
                else:
                    is_intra = False
                    is_ut = False
            else:
                buyer_gstin = customer.gstin if customer else None
                shipping_addr = getattr(customer, "shipping_address", None) if customer else None
                ctx = SupplyResolutionContext(
                    supplier_state_code=supplier_state,
                    buyer_gstin=buyer_gstin,
                    shipping_address=shipping_addr,
                )
                res = self._pos_resolution_service.resolve_supply(ctx)
                pos = res.place_of_supply
                is_intra = res.is_intra_state
                is_ut = res.is_utgst

            invoice.place_of_supply = pos

            # Recalculate immutable tax snapshot at issuance
            supply_type = (
                GSTSupplyType.INTRA_STATE if is_intra else GSTSupplyType.INTER_STATE
            )
            subtotal = Decimal("0.00")
            discount_amount = Decimal("0.00")
            tax_amount = Decimal("0.00")

            for line in invoice.lines:
                gross = self._money(line.quantity * line.unit_price)
                disc = self._money(line.discount)
                taxable_line_amount = self._money(gross - disc)
                breakdown = self._gst_calculation_service.calculate_line(
                    GSTCalculationLineInput(
                        description=line.description,
                        quantity=Decimal("1.00"),
                        unit_amount=taxable_line_amount,
                        tax_rate=line.tax_rate,
                        supply_type=supply_type,
                        is_utgst=is_ut,
                    ),
                    default_supply_type=supply_type,
                    is_utgst=is_ut,
                )
                line.cgst_amount = breakdown.cgst_amount
                line.sgst_amount = breakdown.sgst_amount
                line.igst_amount = breakdown.igst_amount
                line.utgst_amount = breakdown.utgst_amount
                line.cess_amount = breakdown.cess_amount
                line.line_total = breakdown.line_total

                subtotal += gross
                discount_amount += disc
                tax_amount += breakdown.tax_amount

            taxable_amount = self._money(subtotal - discount_amount)
            invoice.subtotal = self._money(subtotal)
            invoice.discount_amount = self._money(discount_amount)
            invoice.taxable_amount = taxable_amount
            invoice.tax_amount = self._money(tax_amount)
            invoice.total_amount = self._money(taxable_amount + tax_amount)

            stock_lines = await self._resolve_stock_lines_for_issuance(uow, invoice)

            invoice = await uow.sales_invoices.mark_status(
                invoice,
                InvoiceStatus.ISSUED,
            )

            if self._stock_engine is not None:
                if stock_lines:
                    if hasattr(self._stock_engine, "issue_sale_lines"):
                        if supports_uow(self._stock_engine.issue_sale_lines):
                            await self._stock_engine.issue_sale_lines(
                                invoice, stock_lines, uow=uow
                            )
                        else:
                            await self._stock_engine.issue_sale_lines(invoice, stock_lines)
                    elif hasattr(self._stock_engine, "issue_sale"):
                        if supports_uow(self._stock_engine.issue_sale):
                            await self._stock_engine.issue_sale(invoice, uow=uow)
                        else:
                            await self._stock_engine.issue_sale(invoice)
                elif not invoice.lines and hasattr(self._stock_engine, "issue_sale"):
                    if supports_uow(self._stock_engine.issue_sale):
                        await self._stock_engine.issue_sale(invoice, uow=uow)
                    else:
                        await self._stock_engine.issue_sale(invoice)

            if self._accounting_kernel is not None:
                if supports_uow(self._accounting_kernel.record_sales_invoice):
                    await self._accounting_kernel.record_sales_invoice(
                        invoice_id,
                        uow=uow,
                    )
                else:
                    await self._accounting_kernel.record_sales_invoice(invoice_id)

            if hasattr(uow, "outbox") and uow.outbox is not None:
                await uow.outbox.add(
                    business_id=invoice.business_id,
                    event_name="sales.invoice.issued",
                    event_payload={
                        "invoice_id": str(invoice.id),
                        "invoice_number": invoice.invoice_number,
                        "business_id": str(invoice.business_id),
                        "total_amount": str(invoice.total_amount),
                        "place_of_supply": invoice.place_of_supply,
                    },
                )

            await uow.commit()
            await self._dispatch_status_event(invoice, "issued")
            reloaded = await uow.sales_invoices.get_by_id(invoice.id)
            return InvoiceResponse.model_validate(reloaded or invoice)

    async def cancel_invoice(self, invoice_id: uuid.UUID) -> InvoiceResponse:
        """Cancel a draft invoice."""
        return await self._transition_invoice(
            invoice_id,
            target_status=InvoiceStatus.CANCELLED,
            allowed_statuses={InvoiceStatus.DRAFT},
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
        invoice = await self._transition_invoice_model(
            invoice_id,
            target_status=target_status,
            allowed_statuses=allowed_statuses,
            event_name=event_name,
        )
        return InvoiceResponse.model_validate(invoice)

    async def _transition_invoice_model(
        self,
        invoice_id: uuid.UUID,
        *,
        target_status: InvoiceStatus,
        allowed_statuses: set[InvoiceStatus],
        event_name: str,
    ) -> SalesInvoice:
        """Apply an invoice lifecycle status transition and return the model."""
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
            await uow.commit()
            await self._dispatch_status_event(invoice, event_name)
            reloaded = await uow.sales_invoices.get_by_id(invoice.id)
            return reloaded or invoice

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

    async def _resolve_supplier_state_code(
        self,
        uow: Any,
        business_id: uuid.UUID,
    ) -> str:
        """Resolve the 2-digit GST state code of the supplier business."""
        if hasattr(uow, "businesses"):
            business = await uow.businesses.get_by_id(business_id)
            if business is not None:
                if getattr(business, "tax_profile", None) and business.tax_profile.gstin:
                    return business.tax_profile.gstin[:2]
                if getattr(business, "address", None) and business.address.state:
                    state_str = str(business.address.state).strip()
                    if len(state_str) == 2 and state_str.isdigit():
                        return state_str
                from app.modules.gst.services.pos_resolution_service import (
                    TransactionClassificationIndeterminateException,
                )

                raise TransactionClassificationIndeterminateException(
                    "Business lacks active GST registration and address state",
                    details={"business_id": str(business_id)},
                )
        return self._default_supplier_state_code

    def _prepare_create_request(
        self,
        request: InvoiceCreateRequest,
        *,
        supplier_state_code: str | None = None,
    ) -> InvoiceCreateRequest:
        """Calculate invoice totals before persistence."""
        invoice_number = request.invoice_number or self._generate_invoice_number(
            request.invoice_date
        )
        supply_type = GSTSupplyType.INTRA_STATE
        is_utgst = False
        place_of_supply = request.place_of_supply
        if place_of_supply:
            place_of_supply = validate_state_code(place_of_supply)
            supplier_state = supplier_state_code or self._default_supplier_state_code
            if place_of_supply == supplier_state:
                supply_type = GSTSupplyType.INTRA_STATE
                is_utgst = is_utgst_jurisdiction(place_of_supply)
            else:
                supply_type = GSTSupplyType.INTER_STATE
                is_utgst = False

        totals = self._calculate_totals(
            request.lines,
            supply_type=supply_type,
            is_utgst=is_utgst,
        )
        return request.model_copy(
            update={
                "invoice_number": invoice_number,
                "place_of_supply": place_of_supply,
                "status": InvoiceStatus.DRAFT,
                **totals,
            }
        )

    def _prepare_update_request(
        self,
        request: InvoiceUpdateRequest,
        *,
        current_invoice: SalesInvoice | None = None,
        supplier_state_code: str | None = None,
    ) -> InvoiceUpdateRequest:
        """Calculate invoice update totals when lines are supplied."""
        place_of_supply = request.place_of_supply
        if place_of_supply is None and current_invoice is not None:
            place_of_supply = current_invoice.place_of_supply

        supply_type = GSTSupplyType.INTRA_STATE
        is_utgst = False
        if place_of_supply:
            place_of_supply = validate_state_code(place_of_supply)
            supplier_state = supplier_state_code or self._default_supplier_state_code
            if place_of_supply == supplier_state:
                supply_type = GSTSupplyType.INTRA_STATE
                is_utgst = is_utgst_jurisdiction(place_of_supply)
            else:
                supply_type = GSTSupplyType.INTER_STATE
                is_utgst = False

        update_dict: dict[str, Any] = {}
        if request.place_of_supply is not None:
            update_dict["place_of_supply"] = place_of_supply

        if request.lines is not None:
            totals = self._calculate_totals(
                request.lines,
                supply_type=supply_type,
                is_utgst=is_utgst,
            )
            update_dict.update(totals)

        return request.model_copy(update=update_dict)

    def _calculate_totals(
        self,
        lines: list[InvoiceLineRequest],
        *,
        supply_type: GSTSupplyType = GSTSupplyType.INTRA_STATE,
        is_utgst: bool = False,
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
            breakdown = self._gst_calculation_service.calculate_line(
                GSTCalculationLineInput(
                    description=line.description,
                    quantity=Decimal("1.00"),
                    unit_amount=taxable_line_amount,
                    tax_rate=line.tax_rate,
                    supply_type=supply_type,
                    is_utgst=is_utgst,
                ),
                default_supply_type=supply_type,
                is_utgst=is_utgst,
            )
            prepared_lines.append(
                line.model_copy(
                    update={
                        "cgst_amount": breakdown.cgst_amount,
                        "sgst_amount": breakdown.sgst_amount,
                        "igst_amount": breakdown.igst_amount,
                        "utgst_amount": breakdown.utgst_amount,
                        "cess_amount": breakdown.cess_amount,
                        "line_total": breakdown.line_total,
                    }
                )
            )
            subtotal += gross
            discount_amount += discount
            tax_amount += breakdown.tax_amount

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

    async def _resolve_stock_lines_for_issuance(
        self,
        uow: Any,
        invoice: SalesInvoice,
    ) -> list[Any]:
        """Classify invoice lines via catalog items and resolve required stock lines."""
        from app.modules.catalog.models.enums import CatalogItemStatus, ItemType
        from app.modules.inventory.services.stock_engine import StockLine

        stock_lines: list[StockLine] = []

        for line in invoice.lines:
            if line.catalog_item_id is None:
                raise SalesInvoiceValidationException(
                    f"Line '{line.description}' is not linked to a catalog item. "
                    "Drafts with unclassified lines cannot be issued.",
                    details={"line_id": str(line.id)},
                )

            catalog_item = getattr(line, "catalog_item", None)
            if (
                catalog_item is None
                and hasattr(uow, "catalog_items")
                and uow.catalog_items is not None
            ):
                catalog_item = await uow.catalog_items.get_by_id(line.catalog_item_id)

            if catalog_item is None or catalog_item.business_id != invoice.business_id:
                raise SalesInvoiceValidationException(
                    f"Catalog item for line '{line.description}' was not found or does not belong to business.",
                    details={"catalog_item_id": str(line.catalog_item_id)},
                )

            if catalog_item.status != CatalogItemStatus.ACTIVE:
                raise SalesInvoiceValidationException(
                    f"Catalog item '{catalog_item.name}' is archived and cannot be issued.",
                    details={"catalog_item_id": str(catalog_item.id)},
                )

            if catalog_item.item_type == ItemType.SERVICE:
                continue

            from sqlalchemy import inspect
            item_state = inspect(catalog_item)
            profile = (
                catalog_item.inventory_profile
                if (item_state and "inventory_profile" in item_state.dict)
                else None
            )
            if (
                profile is None
                and hasattr(uow, "inventory_profiles")
                and uow.inventory_profiles is not None
            ):
                profile = await uow.inventory_profiles.get_by_catalog_item_id(
                    catalog_item.id
                )

            if profile is None or not profile.stock_tracking:
                continue

            if profile.legacy_product_id is None:
                raise SalesInvoiceValidationException(
                    f"Stock-tracked item '{catalog_item.name}' does not have a linked inventory product mapping.",
                    details={"catalog_item_id": str(catalog_item.id)},
                )

            warehouse_id = line.warehouse_id or profile.default_warehouse_id
            if warehouse_id is None and hasattr(uow, "warehouses") and uow.warehouses is not None:
                try:
                    warehouses_page = await uow.warehouses.list(
                        business_id=invoice.business_id,
                        is_active=True,
                    )
                    active_warehouses = (
                        warehouses_page.items
                        if hasattr(warehouses_page, "items")
                        else list(warehouses_page)
                    )
                    if len(active_warehouses) == 1:
                        warehouse_id = active_warehouses[0].id
                except Exception:
                    pass

            if warehouse_id is None:
                raise SalesInvoiceValidationException(
                    f"Warehouse could not be resolved for stock-tracked item '{catalog_item.name}'.",
                    details={"catalog_item_id": str(catalog_item.id)},
                )

            stock_lines.append(
                StockLine(
                    product_id=profile.legacy_product_id,
                    warehouse_id=warehouse_id,
                    quantity=Decimal(str(line.quantity)),
                    description=line.description,
                )
            )

        return stock_lines
