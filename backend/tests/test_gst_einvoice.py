"""Tests for GST e-invoicing framework."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Self, cast

import pytest
from fastapi.testclient import TestClient

from app.common.events import Event, EventDispatcher
from app.main import create_app
from app.modules.gst.einvoice.api.dependencies import (
    get_einvoice_service,
    get_einvoice_unit_of_work,
)
from app.modules.gst.einvoice.events import (
    EWayBillCancelledEvent,
    EWayBillGeneratedEvent,
    IRNCancelledEvent,
    IRNGeneratedEvent,
)
from app.modules.gst.einvoice.exceptions import (
    DuplicateIRNException,
    GSTProviderFailureException,
)
from app.modules.gst.einvoice.models import (
    EInvoice,
    EInvoiceQRCode,
    EInvoiceStatus,
    EWayBill,
    EWayBillStatus,
    TransportMode,
)
from app.modules.gst.einvoice.providers import GSTProviderClient, MockGSTProvider
from app.modules.gst.einvoice.schemas import (
    EInvoiceCancelRequest,
    EInvoiceGenerateRequest,
    EWayBillCancelRequest,
    EWayBillGenerateRequest,
)
from app.modules.gst.einvoice.services import EInvoiceService, EInvoiceUnitOfWork
from app.modules.gst.models import GSTRegistration, GSTRegistrationType
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus
from app.modules.sales.models import InvoiceStatus, SalesInvoice, SalesInvoiceLine

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_FORBIDDEN = 403


class CapturingEventDispatcher(EventDispatcher):
    """Event dispatcher that captures events."""

    def __init__(self) -> None:
        """Initialize captured events."""
        super().__init__()
        self.events: list[Event] = []

    async def dispatch(self, event: Event) -> None:
        """Capture dispatched event."""
        self.events.append(event)
        await super().dispatch(event)


class FailingProvider(MockGSTProvider):
    """Provider that fails all IRN generation calls."""

    async def generate_irn(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Raise provider failure."""
        _ = payload
        raise RuntimeError("provider unavailable")


class FakeMembershipRepository:
    """Fake business membership repository."""

    def __init__(self, *, is_member: bool = True) -> None:
        """Initialize membership behavior."""
        self.is_member_result = is_member

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return configured membership response."""
        _ = business_id
        _ = user_id
        return self.is_member_result


@dataclass
class FakeEInvoiceRepository:
    """Fake e-invoice repository."""

    records: list[EInvoice] = field(default_factory=list)
    qr_codes: list[EInvoiceQRCode] = field(default_factory=list)

    async def create(self, e_invoice: EInvoice) -> EInvoice:
        """Persist e-invoice in memory."""
        if e_invoice.id is None:
            e_invoice.id = uuid.uuid4()
        self.records.append(e_invoice)
        return e_invoice

    async def create_qr_code(self, qr_code: EInvoiceQRCode) -> EInvoiceQRCode:
        """Persist QR code in memory."""
        if qr_code.id is None:
            qr_code.id = uuid.uuid4()
        self.qr_codes.append(qr_code)
        return qr_code

    async def get_by_invoice_id(self, invoice_id: uuid.UUID) -> EInvoice | None:
        """Return e-invoice by invoice UUID."""
        return next(
            (record for record in self.records if record.invoice_id == invoice_id),
            None,
        )

    async def get_active_by_invoice_id(
        self,
        invoice_id: uuid.UUID,
    ) -> EInvoice | None:
        """Return active e-invoice by invoice UUID."""
        return next(
            (
                record
                for record in self.records
                if record.invoice_id == invoice_id
                and record.status == EInvoiceStatus.GENERATED
            ),
            None,
        )

    async def get_qr_code(self, invoice_id: uuid.UUID) -> EInvoiceQRCode | None:
        """Return QR code by invoice UUID."""
        return next(
            (qr_code for qr_code in self.qr_codes if qr_code.invoice_id == invoice_id),
            None,
        )

    async def cancel(
        self,
        e_invoice: EInvoice,
        *,
        reason: str,
    ) -> EInvoice:
        """Cancel e-invoice."""
        e_invoice.status = EInvoiceStatus.CANCELLED
        e_invoice.cancel_reason = reason
        return e_invoice


@dataclass
class FakeEWayBillRepository:
    """Fake e-way bill repository."""

    records: list[EWayBill] = field(default_factory=list)

    async def create(self, eway_bill: EWayBill) -> EWayBill:
        """Persist e-way bill in memory."""
        if eway_bill.id is None:
            eway_bill.id = uuid.uuid4()
        self.records.append(eway_bill)
        return eway_bill

    async def get_by_invoice_id(self, invoice_id: uuid.UUID) -> EWayBill | None:
        """Return e-way bill by invoice UUID."""
        return next(
            (record for record in self.records if record.invoice_id == invoice_id),
            None,
        )

    async def get_active_by_invoice_id(
        self,
        invoice_id: uuid.UUID,
    ) -> EWayBill | None:
        """Return active e-way bill by invoice UUID."""
        return next(
            (
                record
                for record in self.records
                if record.invoice_id == invoice_id
                and record.status == EWayBillStatus.GENERATED
            ),
            None,
        )

    async def cancel(
        self,
        eway_bill: EWayBill,
        *,
        reason: str,
    ) -> EWayBill:
        """Cancel e-way bill."""
        eway_bill.status = EWayBillStatus.CANCELLED
        eway_bill.cancel_reason = reason
        return eway_bill


@dataclass
class FakeSalesInvoiceRepository:
    """Fake sales invoice repository."""

    invoices: list[SalesInvoice]

    async def get_by_id(self, invoice_id: uuid.UUID) -> SalesInvoice | None:
        """Return invoice by UUID."""
        return next(
            (invoice for invoice in self.invoices if invoice.id == invoice_id),
            None,
        )


@dataclass
class FakeGSTRegistrationRepository:
    """Fake GST registration repository."""

    registrations: list[GSTRegistration]

    async def get_active_by_business(
        self,
        business_id: uuid.UUID,
    ) -> GSTRegistration | None:
        """Return active GST registration."""
        return next(
            (
                registration
                for registration in self.registrations
                if registration.business_id == business_id and registration.is_active
            ),
            None,
        )


class FakeEInvoiceUnitOfWork:
    """Fake Unit of Work for e-invoicing tests."""

    def __init__(
        self,
        *,
        invoice: SalesInvoice,
        registration: GSTRegistration,
        is_member: bool = True,
    ) -> None:
        """Initialize fake repositories."""
        self.einvoices = FakeEInvoiceRepository()
        self.eway_bills = FakeEWayBillRepository()
        self.sales_invoices = FakeSalesInvoiceRepository([invoice])
        self.gst_registrations = FakeGSTRegistrationRepository([registration])
        self.business_memberships = FakeMembershipRepository(is_member=is_member)
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        """Enter transaction."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Rollback fake transaction on exception or missing commit."""
        _ = exc
        _ = traceback
        if exc_type is not None or not self.committed:
            self.rolled_back = True

    async def commit(self) -> None:
        """Mark fake transaction committed."""
        self.committed = True


def build_invoice(business_id: uuid.UUID) -> SalesInvoice:
    """Build eligible sales invoice with GST breakdown."""
    invoice_id = uuid.uuid4()
    return SalesInvoice(
        id=invoice_id,
        business_id=business_id,
        customer_id=uuid.uuid4(),
        invoice_number="INV-001",
        invoice_date=date(2026, 4, 10),
        status=InvoiceStatus.ISSUED,
        subtotal=Decimal("1000.00"),
        discount_amount=Decimal("0.00"),
        taxable_amount=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=invoice_id,
                description="Consulting",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1000.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("18.00"),
                cgst_amount=Decimal("90.00"),
                sgst_amount=Decimal("90.00"),
                igst_amount=Decimal("0.00"),
                cess_amount=Decimal("0.00"),
                line_total=Decimal("1180.00"),
            )
        ],
    )


def build_registration(business_id: uuid.UUID) -> GSTRegistration:
    """Build active GST registration."""
    return GSTRegistration(
        id=uuid.uuid4(),
        business_id=business_id,
        gstin="29ABCDE1234F1Z5",
        legal_name="Aarav Technologies Private Limited",
        trade_name="Aarav Tech",
        registration_type=GSTRegistrationType.REGULAR,
        state_code="29",
        registration_date=date(2026, 4, 1),
        is_composition_scheme=False,
        is_active=True,
    )


def build_user() -> IdentityUser:
    """Build authenticated user."""
    return IdentityUser(
        id=uuid.uuid4(),
        email="owner@example.com",
        first_name="Aarav",
        last_name="Sharma",
        display_name="Aarav Sharma",
        status=UserStatus.ACTIVE,
    )


def build_service_state(
    *,
    provider_factory: Callable[[str], GSTProviderClient] | None = None,
    is_member: bool = True,
) -> tuple[
    uuid.UUID,
    SalesInvoice,
    FakeEInvoiceUnitOfWork,
    EInvoiceService,
    CapturingEventDispatcher,
]:
    """Build fake service graph."""
    business_id = uuid.uuid4()
    invoice = build_invoice(business_id)
    registration = build_registration(business_id)
    uow = FakeEInvoiceUnitOfWork(
        invoice=invoice,
        registration=registration,
        is_member=is_member,
    )
    dispatcher = CapturingEventDispatcher()
    service = EInvoiceService(
        unit_of_work_factory=lambda: cast(EInvoiceUnitOfWork, uow),
        event_dispatcher=dispatcher,
        provider_factory=provider_factory,
    )
    return business_id, invoice, uow, service, dispatcher


@pytest.mark.asyncio
async def test_mock_provider_irn_generation_and_qr() -> None:
    """Service generates IRN and QR data through the mock provider."""
    _business_id, invoice, uow, service, dispatcher = build_service_state()

    result = await service.generate_irn(
        EInvoiceGenerateRequest(invoice_id=invoice.id)
    )

    assert result.invoice_id == invoice.id
    assert result.irn
    assert uow.einvoices.qr_codes[0].qr_content.startswith("IRN:")
    assert uow.committed is True
    assert isinstance(dispatcher.events[0], IRNGeneratedEvent)


@pytest.mark.asyncio
async def test_duplicate_irn_rejected() -> None:
    """Duplicate active IRNs are rejected."""
    _business_id, invoice, _uow, service, _dispatcher = build_service_state()

    await service.generate_irn(EInvoiceGenerateRequest(invoice_id=invoice.id))

    with pytest.raises(DuplicateIRNException):
        await service.generate_irn(EInvoiceGenerateRequest(invoice_id=invoice.id))


@pytest.mark.asyncio
async def test_irn_and_eway_bill_cancellation() -> None:
    """Service cancels IRNs and e-way bills."""
    _business_id, invoice, _uow, service, dispatcher = build_service_state()
    await service.generate_irn(EInvoiceGenerateRequest(invoice_id=invoice.id))
    eway_bill = await service.generate_eway_bill(
        EWayBillGenerateRequest(
            invoice_id=invoice.id,
            vehicle_number="KA01AB1234",
        )
    )

    cancelled_eway = await service.cancel_eway_bill(
        EWayBillCancelRequest(invoice_id=invoice.id, reason="Transport cancelled")
    )
    cancelled_irn = await service.cancel_irn(
        EInvoiceCancelRequest(invoice_id=invoice.id, reason="Invoice cancelled")
    )

    assert eway_bill.eway_bill_number == cancelled_eway.eway_bill_number
    assert cancelled_eway.status == EWayBillStatus.CANCELLED
    assert cancelled_irn.status == EInvoiceStatus.CANCELLED
    assert any(isinstance(event, EWayBillCancelledEvent) for event in dispatcher.events)
    assert any(isinstance(event, IRNCancelledEvent) for event in dispatcher.events)


@pytest.mark.asyncio
async def test_generate_irn_with_optional_eway_bill_and_status_lookup() -> None:
    """IRN workflow can generate e-way bill and return status."""
    _business_id, invoice, _uow, service, dispatcher = build_service_state()

    await service.generate_irn(
        EInvoiceGenerateRequest(
            invoice_id=invoice.id,
            generate_eway_bill=True,
            vehicle_number="KA01AB1234",
            transport_mode=TransportMode.ROAD,
        )
    )
    status = await service.get_status(invoice.id)

    assert status.e_invoice is not None
    assert status.qr_code is not None
    assert status.eway_bill is not None
    assert status.provider_status["status"] == "available"
    assert any(isinstance(event, EWayBillGeneratedEvent) for event in dispatcher.events)


@pytest.mark.asyncio
async def test_provider_failure_rolls_back_and_retry_succeeds() -> None:
    """Provider failure rolls back and retry can succeed with a healthy provider."""
    _business_id, invoice, uow, failing_service, _dispatcher = build_service_state(
        provider_factory=lambda _name: FailingProvider()
    )

    with pytest.raises(GSTProviderFailureException):
        await failing_service.generate_irn(
            EInvoiceGenerateRequest(invoice_id=invoice.id)
        )

    assert uow.rolled_back is True
    assert uow.einvoices.records == []

    healthy_dispatcher = CapturingEventDispatcher()
    healthy_service = EInvoiceService(
        unit_of_work_factory=lambda: cast(EInvoiceUnitOfWork, uow),
        event_dispatcher=healthy_dispatcher,
    )
    result = await healthy_service.generate_irn(
        EInvoiceGenerateRequest(invoice_id=invoice.id)
    )

    assert result.irn
    assert uow.committed is True


def test_einvoice_api_and_business_isolation() -> None:
    """API exposes e-invoice endpoints and enforces business membership."""
    app = create_app(initialize_resources=False)
    business_id, invoice, uow, service, _dispatcher = build_service_state()
    app.dependency_overrides[get_current_user] = build_user
    app.dependency_overrides[get_einvoice_unit_of_work] = lambda: uow
    app.dependency_overrides[get_einvoice_service] = lambda: service

    with TestClient(app) as client:
        generate_response = client.post(
            "/api/v1/gst/einvoice/generate",
            params={"business_id": str(business_id)},
            json={"invoice_id": str(invoice.id)},
        )
        status_response = client.get(
            f"/api/v1/gst/einvoice/{invoice.id}",
            params={"business_id": str(business_id)},
        )
        schema = client.get("/openapi.json").json()

    assert generate_response.status_code == HTTP_CREATED
    assert status_response.status_code == HTTP_OK
    assert "/api/v1/gst/einvoice/generate" in schema["paths"]
    assert "/api/v1/gst/einvoice/cancel" in schema["paths"]
    assert "/api/v1/gst/ewaybill/generate" in schema["paths"]
    assert "/api/v1/gst/ewaybill/cancel" in schema["paths"]
    assert f"/api/v1/gst/einvoice/{'{'}invoice_id{'}'}" in schema["paths"]

    denied_business_id, _denied_invoice, denied_uow, denied_service, _events = (
        build_service_state(is_member=False)
    )
    app.dependency_overrides[get_einvoice_unit_of_work] = lambda: denied_uow
    app.dependency_overrides[get_einvoice_service] = lambda: denied_service

    with TestClient(app) as client:
        denied_response = client.post(
            "/api/v1/gst/einvoice/generate",
            params={"business_id": str(denied_business_id)},
            json={"invoice_id": str(invoice.id)},
        )

    assert denied_response.status_code == HTTP_FORBIDDEN
