"""Tests for Sales payment API router."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus
from app.modules.sales.api.dependencies import (
    get_payment_service,
    get_sales_unit_of_work,
)
from app.modules.sales.models import InvoiceStatus, Payment, PaymentMethod, SalesInvoice
from app.modules.sales.schemas import PaymentCreateRequest, PaymentResponse

HTTP_CREATED = 201
HTTP_FORBIDDEN = 403
HTTP_NO_CONTENT = 204
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401


class FakeMembershipRepository:
    """Fake business membership repository."""

    def __init__(self, *, is_member: bool = True) -> None:
        """Initialize membership result."""
        self.member = is_member

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return configured membership result."""
        _ = business_id
        _ = user_id
        return self.member


class FakeInvoiceRepository:
    """Fake invoice repository."""

    def __init__(self, invoice: SalesInvoice) -> None:
        """Initialize with invoice."""
        self.invoice = invoice

    async def get_by_id(self, invoice_id: uuid.UUID) -> SalesInvoice | None:
        """Return invoice by id."""
        if self.invoice.id == invoice_id:
            return self.invoice
        return None


class FakePaymentRepository:
    """Fake payment repository."""

    def __init__(self, payment: Payment) -> None:
        """Initialize with payment."""
        self.payment = payment

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        """Return payment by id."""
        if self.payment.id == payment_id:
            return self.payment
        return None


class FakeSalesUnitOfWork:
    """Fake Sales Unit of Work for payment API tests."""

    def __init__(
        self,
        *,
        invoice: SalesInvoice,
        payment: Payment,
        is_member: bool = True,
    ) -> None:
        """Initialize fake repositories."""
        self.sales_invoices = FakeInvoiceRepository(invoice)
        self.payments = FakePaymentRepository(payment)
        self.business_memberships = FakeMembershipRepository(is_member=is_member)

    async def __aenter__(self) -> "FakeSalesUnitOfWork":
        """Enter fake transaction scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit fake transaction scope."""


class FakePaymentService:
    """Fake payment service for API tests."""

    def __init__(self, payment: PaymentResponse) -> None:
        """Initialize with payment response."""
        self.payment = payment
        self.recorded_request: PaymentCreateRequest | None = None
        self.updated_request: PaymentCreateRequest | None = None
        self.deleted_payment_id: uuid.UUID | None = None

    async def record_payment(self, request: PaymentCreateRequest) -> PaymentResponse:
        """Return recorded payment."""
        self.recorded_request = request
        return self.payment

    async def update_payment(
        self,
        payment_id: uuid.UUID,
        request: PaymentCreateRequest,
    ) -> PaymentResponse:
        """Return updated payment."""
        _ = payment_id
        self.updated_request = request
        return self.payment.model_copy(update={"amount": request.amount})

    async def delete_payment(self, payment_id: uuid.UUID) -> None:
        """Record deleted payment id."""
        self.deleted_payment_id = payment_id


def build_user() -> IdentityUser:
    """Build an authenticated user."""
    return IdentityUser(
        id=uuid.uuid4(),
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=UserStatus.ACTIVE,
        failed_login_attempts=0,
    )


def build_invoice() -> SalesInvoice:
    """Build a sales invoice."""
    return SalesInvoice(
        id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        invoice_number="INV-0001",
        invoice_date=date(2026, 4, 1),
        status=InvoiceStatus.ISSUED,
        total_amount=Decimal("1000.00"),
    )


def build_payment(invoice_id: uuid.UUID) -> Payment:
    """Build a payment."""
    return Payment(
        id=uuid.uuid4(),
        invoice_id=invoice_id,
        payment_date=date(2026, 4, 10),
        amount=Decimal("500.00"),
        payment_method=PaymentMethod.UPI,
        reference_number="UPI-123",
    )


def build_payment_payload(invoice_id: uuid.UUID) -> dict[str, object]:
    """Build a payment request payload."""
    return {
        "invoice_id": str(invoice_id),
        "payment_date": "2026-04-10",
        "amount": "500.00",
        "payment_method": "upi",
        "reference_number": "UPI-123",
    }


def build_client(
    *,
    authenticated: bool = True,
    is_member: bool = True,
) -> tuple[TestClient, FakeSalesUnitOfWork, FakePaymentService, IdentityUser]:
    """Build a test client with payment dependency overrides."""
    app = create_app(initialize_resources=False)
    invoice = build_invoice()
    payment = build_payment(invoice.id)
    uow = FakeSalesUnitOfWork(
        invoice=invoice,
        payment=payment,
        is_member=is_member,
    )
    service = FakePaymentService(PaymentResponse.model_validate(payment))
    user = build_user()

    app.dependency_overrides[get_sales_unit_of_work] = lambda: uow
    app.dependency_overrides[get_payment_service] = lambda: service
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), uow, service, user


def test_record_payment_endpoint() -> None:
    """Record payment endpoint delegates to service."""
    client, uow, service, _user = build_client()

    with client:
        response = client.post(
            "/api/v1/sales/payments",
            json=build_payment_payload(uow.sales_invoices.invoice.id),
        )

    assert response.status_code == HTTP_CREATED
    assert response.json()["data"]["amount"] == "500.00"
    assert service.recorded_request is not None


def test_get_payment_endpoint() -> None:
    """Get payment endpoint returns payment response."""
    client, uow, _service, _user = build_client()

    with client:
        response = client.get(f"/api/v1/sales/payments/{uow.payments.payment.id}")

    assert response.status_code == HTTP_OK
    assert response.json()["data"]["reference_number"] == "UPI-123"


def test_update_payment_endpoint() -> None:
    """Update payment endpoint delegates to service."""
    client, uow, service, _user = build_client()

    with client:
        response = client.patch(
            f"/api/v1/sales/payments/{uow.payments.payment.id}",
            json=build_payment_payload(uow.sales_invoices.invoice.id),
        )

    assert response.status_code == HTTP_OK
    assert response.json()["data"]["amount"] == "500.00"
    assert service.updated_request is not None


def test_delete_payment_endpoint() -> None:
    """Delete payment endpoint delegates to service."""
    client, uow, service, _user = build_client()

    with client:
        response = client.delete(f"/api/v1/sales/payments/{uow.payments.payment.id}")

    assert response.status_code == HTTP_NO_CONTENT
    assert response.content == b""
    assert service.deleted_payment_id == uow.payments.payment.id


def test_unauthorized_payment_access() -> None:
    """Payment endpoints require authentication."""
    client, uow, _service, _user = build_client(authenticated=False)

    with client:
        response = client.get(f"/api/v1/sales/payments/{uow.payments.payment.id}")

    assert response.status_code == HTTP_UNAUTHORIZED
    assert response.json()["data"]["code"] == "authentication.required"


def test_payment_business_isolation() -> None:
    """Non-members cannot access payment resources."""
    client, uow, _service, _user = build_client(is_member=False)

    with client:
        response = client.get(f"/api/v1/sales/payments/{uow.payments.payment.id}")

    assert response.status_code == HTTP_FORBIDDEN
    assert response.json()["data"]["code"] == "business.not_member"


def test_openapi_documents_payment_routes() -> None:
    """OpenAPI includes payment route documentation."""
    client, _uow, _service, _user = build_client()

    with client:
        schema = client.get("/openapi.json").json()

    assert "/api/v1/sales/payments" in schema["paths"]
    assert "/api/v1/sales/payments/{payment_id}" in schema["paths"]
    assert schema["paths"]["/api/v1/sales/payments"]["post"]["summary"] == (
        "Record payment"
    )
    assert schema["paths"]["/api/v1/sales/payments/{payment_id}"]["delete"][
        "summary"
    ] == "Delete payment"
