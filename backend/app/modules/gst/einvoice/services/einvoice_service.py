"""E-invoicing and e-way bill service."""

import uuid
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from app.common.events import EventDispatcher
from app.modules.gst.einvoice.events import (
    EWayBillCancelledEvent,
    EWayBillGeneratedEvent,
    IRNCancelledEvent,
    IRNGeneratedEvent,
)
from app.modules.gst.einvoice.exceptions import (
    DuplicateEWayBillException,
    DuplicateIRNException,
    EInvoiceNotFoundException,
    EInvoiceValidationException,
    EWayBillNotFoundException,
    GSTProviderFailureException,
)
from app.modules.gst.einvoice.models import (
    EInvoice,
    EInvoiceQRCode,
    EInvoiceStatus,
    EWayBill,
    EWayBillStatus,
)
from app.modules.gst.einvoice.providers import GSTProviderClient, MockGSTProvider
from app.modules.gst.einvoice.schemas import (
    EInvoiceCancelRequest,
    EInvoiceGenerateRequest,
    EInvoiceQRCodeResponse,
    EInvoiceResponse,
    EInvoiceStatusResponse,
    EWayBillCancelRequest,
    EWayBillGenerateRequest,
    EWayBillResponse,
)
from app.modules.gst.models import GSTRegistration
from app.modules.sales.models import InvoiceStatus, SalesInvoice

POSTED_INVOICE_STATUSES = {
    InvoiceStatus.ISSUED,
    InvoiceStatus.PARTIALLY_PAID,
    InvoiceStatus.PAID,
}
ZERO_AMOUNT = Decimal("0.00")


class EInvoiceRepositoryProtocol(Protocol):
    """Repository behavior required for e-invoices."""

    async def create(self, e_invoice: EInvoice) -> EInvoice:
        """Persist an e-invoice."""
        ...

    async def create_qr_code(self, qr_code: EInvoiceQRCode) -> EInvoiceQRCode:
        """Persist QR code data."""
        ...

    async def get_by_invoice_id(self, invoice_id: uuid.UUID) -> EInvoice | None:
        """Return e-invoice by invoice UUID."""
        ...

    async def get_active_by_invoice_id(
        self,
        invoice_id: uuid.UUID,
    ) -> EInvoice | None:
        """Return active e-invoice by invoice UUID."""
        ...

    async def get_qr_code(self, invoice_id: uuid.UUID) -> EInvoiceQRCode | None:
        """Return QR code by invoice UUID."""
        ...

    async def cancel(
        self,
        e_invoice: EInvoice,
        *,
        reason: str,
    ) -> EInvoice:
        """Cancel an e-invoice."""
        ...


class EWayBillRepositoryProtocol(Protocol):
    """Repository behavior required for e-way bills."""

    async def create(self, eway_bill: EWayBill) -> EWayBill:
        """Persist an e-way bill."""
        ...

    async def get_by_invoice_id(self, invoice_id: uuid.UUID) -> EWayBill | None:
        """Return e-way bill by invoice UUID."""
        ...

    async def get_active_by_invoice_id(
        self,
        invoice_id: uuid.UUID,
    ) -> EWayBill | None:
        """Return active e-way bill by invoice UUID."""
        ...

    async def cancel(
        self,
        eway_bill: EWayBill,
        *,
        reason: str,
    ) -> EWayBill:
        """Cancel an e-way bill."""
        ...


class SalesInvoiceRepositoryProtocol(Protocol):
    """Repository behavior required for sales invoices."""

    async def get_by_id(self, invoice_id: uuid.UUID) -> SalesInvoice | None:
        """Return a sales invoice by UUID."""
        ...


class GSTRegistrationRepositoryProtocol(Protocol):
    """Repository behavior required for GST registrations."""

    async def get_active_by_business(
        self,
        business_id: uuid.UUID,
    ) -> GSTRegistration | None:
        """Return active registration for a business."""
        ...


class EInvoiceUnitOfWork(Protocol):
    """Unit of Work contract for e-invoicing."""

    einvoices: EInvoiceRepositoryProtocol
    eway_bills: EWayBillRepositoryProtocol
    sales_invoices: SalesInvoiceRepositoryProtocol
    gst_registrations: GSTRegistrationRepositoryProtocol

    async def __aenter__(self) -> "EInvoiceUnitOfWork":
        """Enter transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit transaction scope."""
        ...

    async def commit(self) -> None:
        """Commit transaction."""
        ...


UnitOfWorkFactory = Callable[[], EInvoiceUnitOfWork]
ProviderFactory = Callable[[str], GSTProviderClient]


class EInvoiceService:
    """Coordinate GST e-invoice and e-way bill provider workflows."""

    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        event_dispatcher: EventDispatcher,
        provider_factory: ProviderFactory | None = None,
    ) -> None:
        """Initialize dependencies."""
        self._unit_of_work_factory = unit_of_work_factory
        self._event_dispatcher = event_dispatcher
        self._provider_factory = provider_factory or self._default_provider_factory

    async def generate_irn(
        self,
        request: EInvoiceGenerateRequest,
    ) -> EInvoiceResponse:
        """Generate and persist an IRN for a sales invoice."""
        async with self._unit_of_work_factory() as uow:
            invoice = await self._get_valid_invoice(uow, request.invoice_id)
            await self._ensure_active_registration(uow, invoice.business_id)
            await self._ensure_gst_calculated(invoice)
            if await uow.einvoices.get_active_by_invoice_id(invoice.id) is not None:
                raise DuplicateIRNException("Invoice already has an active IRN")

            provider = self._provider_factory(request.provider_name)
            request_payload = self._build_irn_payload(invoice)
            response_payload = await self._provider_call(
                provider.generate_irn,
                request_payload,
            )
            e_invoice = await uow.einvoices.create(
                EInvoice(
                    business_id=invoice.business_id,
                    invoice_id=invoice.id,
                    irn=str(response_payload["irn"]),
                    ack_number=str(response_payload["ack_number"]),
                    ack_date=self._datetime(response_payload["ack_date"]),
                    status=EInvoiceStatus.GENERATED,
                    provider_name=request.provider_name,
                    request_payload=request_payload,
                    response_payload=response_payload,
                )
            )
            await uow.einvoices.create_qr_code(
                EInvoiceQRCode(
                    invoice_id=invoice.id,
                    qr_content=str(response_payload["qr_content"]),
                    hash_value=str(response_payload["qr_hash"]),
                )
            )
            await self._event_dispatcher.dispatch(
                IRNGeneratedEvent(
                    business_id=invoice.business_id,
                    invoice_id=invoice.id,
                    irn=e_invoice.irn,
                )
            )
            if request.generate_eway_bill:
                await self._generate_eway_bill_in_scope(
                    uow,
                    invoice,
                    provider,
                    EWayBillGenerateRequest(
                        invoice_id=invoice.id,
                        provider_name=request.provider_name,
                        vehicle_number=request.vehicle_number,
                        transport_mode=request.transport_mode,
                    ),
                )
            await uow.commit()
            return EInvoiceResponse.model_validate(e_invoice)

    async def cancel_irn(
        self,
        request: EInvoiceCancelRequest,
    ) -> EInvoiceResponse:
        """Cancel an active IRN."""
        async with self._unit_of_work_factory() as uow:
            e_invoice = await uow.einvoices.get_active_by_invoice_id(
                request.invoice_id
            )
            if e_invoice is None:
                raise EInvoiceNotFoundException("Active e-invoice was not found")
            provider = self._provider_factory(e_invoice.provider_name)
            await self._provider_call(
                provider.cancel_irn,
                {"invoice_id": str(request.invoice_id), "irn": e_invoice.irn},
            )
            cancelled = await uow.einvoices.cancel(
                e_invoice,
                reason=request.reason,
            )
            await self._event_dispatcher.dispatch(
                IRNCancelledEvent(
                    business_id=cancelled.business_id,
                    invoice_id=cancelled.invoice_id,
                    irn=cancelled.irn,
                )
            )
            await uow.commit()
            return EInvoiceResponse.model_validate(cancelled)

    async def generate_eway_bill(
        self,
        request: EWayBillGenerateRequest,
    ) -> EWayBillResponse:
        """Generate and persist an e-way bill."""
        async with self._unit_of_work_factory() as uow:
            invoice = await self._get_valid_invoice(uow, request.invoice_id)
            await self._ensure_active_registration(uow, invoice.business_id)
            if await uow.einvoices.get_active_by_invoice_id(invoice.id) is None:
                raise EInvoiceValidationException(
                    "IRN must be generated before e-way bill"
                )
            provider = self._provider_factory(request.provider_name)
            eway_bill = await self._generate_eway_bill_in_scope(
                uow,
                invoice,
                provider,
                request,
            )
            await uow.commit()
            return EWayBillResponse.model_validate(eway_bill)

    async def cancel_eway_bill(
        self,
        request: EWayBillCancelRequest,
    ) -> EWayBillResponse:
        """Cancel an active e-way bill."""
        async with self._unit_of_work_factory() as uow:
            eway_bill = await uow.eway_bills.get_active_by_invoice_id(
                request.invoice_id
            )
            if eway_bill is None:
                raise EWayBillNotFoundException("Active e-way bill was not found")
            provider_name = "mock"
            e_invoice = await uow.einvoices.get_by_invoice_id(request.invoice_id)
            if e_invoice is not None:
                provider_name = e_invoice.provider_name
            provider = self._provider_factory(provider_name)
            await self._provider_call(
                provider.cancel_eway_bill,
                {
                    "invoice_id": str(request.invoice_id),
                    "eway_bill_number": eway_bill.eway_bill_number,
                },
            )
            cancelled = await uow.eway_bills.cancel(
                eway_bill,
                reason=request.reason,
            )
            invoice = await uow.sales_invoices.get_by_id(request.invoice_id)
            business_id = (
                invoice.business_id if invoice is not None else uuid.UUID(int=0)
            )
            await self._event_dispatcher.dispatch(
                EWayBillCancelledEvent(
                    business_id=business_id,
                    invoice_id=cancelled.invoice_id,
                    eway_bill_number=cancelled.eway_bill_number,
                )
            )
            await uow.commit()
            return EWayBillResponse.model_validate(cancelled)

    async def get_status(self, invoice_id: uuid.UUID) -> EInvoiceStatusResponse:
        """Return stored and provider e-invoice status."""
        async with self._unit_of_work_factory() as uow:
            e_invoice = await uow.einvoices.get_by_invoice_id(invoice_id)
            qr_code = await uow.einvoices.get_qr_code(invoice_id)
            eway_bill = await uow.eway_bills.get_by_invoice_id(invoice_id)
            provider_status: dict[str, Any] = {}
            if e_invoice is not None:
                provider = self._provider_factory(e_invoice.provider_name)
                provider_status = await self._provider_call(
                    provider.get_status,
                    {"invoice_id": str(invoice_id), "irn": e_invoice.irn},
                )
            await uow.commit()
        return EInvoiceStatusResponse(
            e_invoice=(
                EInvoiceResponse.model_validate(e_invoice)
                if e_invoice is not None
                else None
            ),
            qr_code=(
                EInvoiceQRCodeResponse.model_validate(qr_code)
                if qr_code is not None
                else None
            ),
            eway_bill=(
                EWayBillResponse.model_validate(eway_bill)
                if eway_bill is not None
                else None
            ),
            provider_status=provider_status,
        )

    async def _generate_eway_bill_in_scope(
        self,
        uow: EInvoiceUnitOfWork,
        invoice: SalesInvoice,
        provider: GSTProviderClient,
        request: EWayBillGenerateRequest,
    ) -> EWayBill:
        """Generate e-way bill inside an existing Unit of Work scope."""
        if await uow.eway_bills.get_active_by_invoice_id(invoice.id) is not None:
            raise DuplicateEWayBillException(
                "Invoice already has an active e-way bill"
            )
        request_payload = {
            "invoice_id": str(invoice.id),
            "business_id": str(invoice.business_id),
            "invoice_number": invoice.invoice_number,
            "total_amount": str(invoice.total_amount),
            "vehicle_number": request.vehicle_number,
            "transport_mode": request.transport_mode,
        }
        response_payload = await self._provider_call(
            provider.generate_eway_bill,
            request_payload,
        )
        eway_bill = await uow.eway_bills.create(
            EWayBill(
                invoice_id=invoice.id,
                eway_bill_number=str(response_payload["eway_bill_number"]),
                valid_from=self._datetime(response_payload["valid_from"]),
                valid_to=self._datetime(response_payload["valid_to"]),
                vehicle_number=response_payload.get("vehicle_number"),
                transport_mode=request.transport_mode,
                status=EWayBillStatus.GENERATED,
            )
        )
        await self._event_dispatcher.dispatch(
            EWayBillGeneratedEvent(
                business_id=invoice.business_id,
                invoice_id=invoice.id,
                eway_bill_number=eway_bill.eway_bill_number,
            )
        )
        return eway_bill

    async def _get_valid_invoice(
        self,
        uow: EInvoiceUnitOfWork,
        invoice_id: uuid.UUID,
    ) -> SalesInvoice:
        """Return a sales invoice eligible for e-invoicing."""
        invoice = await uow.sales_invoices.get_by_id(invoice_id)
        if invoice is None:
            raise EInvoiceNotFoundException("Sales invoice was not found")
        if invoice.status not in POSTED_INVOICE_STATUSES:
            raise EInvoiceValidationException("Sales invoice is not posted")
        if invoice.status == InvoiceStatus.CANCELLED:
            raise EInvoiceValidationException("Cancelled invoices are not eligible")
        return invoice

    async def _ensure_active_registration(
        self,
        uow: EInvoiceUnitOfWork,
        business_id: uuid.UUID,
    ) -> None:
        """Validate active GST registration exists for the business."""
        registration = await uow.gst_registrations.get_active_by_business(business_id)
        if registration is None:
            raise EInvoiceValidationException(
                "Active GST registration is required"
            )

    async def _ensure_gst_calculated(self, invoice: SalesInvoice) -> None:
        """Validate stored GST values exist on the invoice."""
        _ = self
        component_total = sum(
            (
                line.cgst_amount
                + line.sgst_amount
                + line.igst_amount
                + line.cess_amount
            )
            for line in invoice.lines
        )
        if invoice.tax_amount > ZERO_AMOUNT and component_total != invoice.tax_amount:
            raise EInvoiceValidationException("Invoice GST breakdown is incomplete")

    def _build_irn_payload(self, invoice: SalesInvoice) -> dict[str, Any]:
        """Build provider-agnostic IRN request payload."""
        return {
            "invoice_id": str(invoice.id),
            "business_id": str(invoice.business_id),
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date.isoformat(),
            "taxable_amount": str(invoice.taxable_amount),
            "tax_amount": str(invoice.tax_amount),
            "total_amount": str(invoice.total_amount),
            "lines": [
                {
                    "description": line.description,
                    "quantity": str(line.quantity),
                    "line_total": str(line.line_total),
                    "cgst_amount": str(line.cgst_amount),
                    "sgst_amount": str(line.sgst_amount),
                    "igst_amount": str(line.igst_amount),
                    "cess_amount": str(line.cess_amount),
                }
                for line in invoice.lines
            ],
        }

    async def _provider_call(
        self,
        operation: Callable[[dict[str, Any]], Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Wrap provider calls in framework exceptions."""
        try:
            response = await operation(payload)
        except Exception as exc:
            raise GSTProviderFailureException(
                "GST provider operation failed",
                details={"provider_error": str(exc)},
            ) from exc
        if not isinstance(response, dict):
            raise GSTProviderFailureException("GST provider returned invalid payload")
        return response

    def _default_provider_factory(self, provider_name: str) -> GSTProviderClient:
        """Return configured provider client."""
        if provider_name == MockGSTProvider.provider_name:
            return MockGSTProvider()
        raise GSTProviderFailureException(
            "GST provider is not configured",
            details={"provider_name": provider_name},
        )

    def _datetime(self, value: object) -> datetime:
        """Coerce provider datetime payload."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        raise GSTProviderFailureException("GST provider returned invalid timestamp")
