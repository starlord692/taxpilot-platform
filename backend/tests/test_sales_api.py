"""Tests for Sales API router."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.common.pagination import Page, PaginationParams
from app.main import create_app
from app.modules.business.models import BusinessMembership
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus
from app.modules.sales.api.dependencies import (
    get_sales_invoice_service,
    get_sales_unit_of_work,
)
from app.modules.sales.models import (
    Customer,
    InvoiceStatus,
    SalesInvoice,
    SalesInvoiceLine,
)
from app.modules.sales.schemas import (
    CustomerCreateRequest,
    CustomerUpdateRequest,
    InvoiceCreateRequest,
    InvoiceResponse,
    InvoiceUpdateRequest,
)
from tests.support.business_context import FakeBusinessRepository

HTTP_CREATED = 201
HTTP_FORBIDDEN = 403
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401


class FakeMembershipRepository:
    """Fake business membership repository."""

    def __init__(self, *, is_member: bool = True) -> None:
        """Initialize membership result."""
        self.member = is_member
        self.business_id: uuid.UUID | None = None
        self.user_id: uuid.UUID | None = None

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return configured membership result."""
        self.business_id = business_id
        self.user_id = user_id
        return self.member

    async def get_membership(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> BusinessMembership | None:
        """Return configured active membership result."""
        self.business_id = business_id
        self.user_id = user_id
        if not self.member:
            return None
        return BusinessMembership(
            id=uuid.uuid4(),
            business_id=business_id,
            user_id=user_id,
            role="member",
        )


class FakeCustomerRepository:
    """Fake customer repository."""

    def __init__(self, customer: Customer) -> None:
        """Initialize with a customer."""
        self.customer = customer
        self.created_request: CustomerCreateRequest | None = None
        self.updated_request: CustomerUpdateRequest | None = None

    async def create(self, request: CustomerCreateRequest) -> Customer:
        """Create a fake customer."""
        self.created_request = request
        self.customer.business_id = request.business_id
        self.customer.customer_code = request.customer_code
        self.customer.name = request.name
        return self.customer

    async def update(
        self,
        customer: Customer,
        request: CustomerUpdateRequest,
    ) -> Customer:
        """Update a fake customer."""
        self.updated_request = request
        if request.name is not None:
            customer.name = request.name
        return customer

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        """Return fake customer by id."""
        if self.customer.id == customer_id:
            return self.customer
        return None

    async def exists_by_code(
        self,
        *,
        business_id: uuid.UUID,
        customer_code: str,
    ) -> bool:
        """Return no duplicate code."""
        _ = business_id
        _ = customer_code
        return False

    async def exists_by_email(
        self,
        *,
        business_id: uuid.UUID,
        email: str,
    ) -> bool:
        """Return no duplicate email."""
        _ = business_id
        _ = email
        return False

    async def list_business_customers(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams,
    ) -> Page[Customer]:
        """Return paginated fake customers."""
        _ = business_id
        return Page.create(items=[self.customer], total=1, params=pagination)


class FakeInvoiceRepository:
    """Fake invoice repository."""

    def __init__(self, invoice: SalesInvoice) -> None:
        """Initialize with an invoice."""
        self.invoice = invoice

    async def get_by_id(self, invoice_id: uuid.UUID) -> SalesInvoice | None:
        """Return fake invoice by id."""
        if self.invoice.id == invoice_id:
            return self.invoice
        return None

    async def list_business_invoices(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams,
    ) -> Page[SalesInvoice]:
        """Return paginated fake invoices."""
        _ = business_id
        return Page.create(items=[self.invoice], total=1, params=pagination)


class FakeSalesUnitOfWork:
    """Fake Sales Unit of Work for API tests."""

    def __init__(
        self,
        *,
        customer: Customer,
        invoice: SalesInvoice,
        is_member: bool = True,
    ) -> None:
        """Initialize fake repositories."""
        self.customers = FakeCustomerRepository(customer)
        self.sales_invoices = FakeInvoiceRepository(invoice)
        self.businesses = FakeBusinessRepository()
        self.business_memberships = FakeMembershipRepository(is_member=is_member)
        self.committed = False

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

    async def commit(self) -> None:
        """Mark transaction committed."""
        self.committed = True


class FakeSalesInvoiceService:
    """Fake Sales invoice service for API tests."""

    def __init__(self, invoice: InvoiceResponse) -> None:
        """Initialize with an invoice response."""
        self.invoice = invoice
        self.created_request: InvoiceCreateRequest | None = None
        self.updated_request: InvoiceUpdateRequest | None = None

    async def create_invoice(self, request: InvoiceCreateRequest) -> InvoiceResponse:
        """Return created invoice."""
        self.created_request = request
        return self.invoice

    async def update_invoice(
        self,
        invoice_id: uuid.UUID,
        request: InvoiceUpdateRequest,
    ) -> InvoiceResponse:
        """Return updated invoice."""
        _ = invoice_id
        self.updated_request = request
        return self.invoice.model_copy(update={"notes": request.notes})

    async def issue_invoice(self, invoice_id: uuid.UUID) -> InvoiceResponse:
        """Return issued invoice."""
        _ = invoice_id
        return self.invoice.model_copy(update={"status": InvoiceStatus.ISSUED})

    async def cancel_invoice(self, invoice_id: uuid.UUID) -> InvoiceResponse:
        """Return cancelled invoice."""
        _ = invoice_id
        return self.invoice.model_copy(update={"status": InvoiceStatus.CANCELLED})


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


def build_customer(business_id: uuid.UUID) -> Customer:
    """Build a customer."""
    return Customer(
        id=uuid.uuid4(),
        business_id=business_id,
        customer_code="CUST-0001",
        name="Aarav Enterprises",
        email="billing@example.com",
        is_active=True,
    )


def build_invoice(business_id: uuid.UUID, customer_id: uuid.UUID) -> SalesInvoice:
    """Build an invoice."""
    invoice_id = uuid.uuid4()
    return SalesInvoice(
        id=invoice_id,
        business_id=business_id,
        customer_id=customer_id,
        invoice_number="INV-0001",
        invoice_date=date(2026, 4, 1),
        status=InvoiceStatus.DRAFT,
        subtotal=Decimal("1000.00"),
        discount_amount=Decimal("50.00"),
        taxable_amount=Decimal("950.00"),
        tax_amount=Decimal("171.00"),
        total_amount=Decimal("1121.00"),
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=invoice_id,
                description="Monthly bookkeeping",
                quantity=Decimal("2.00"),
                unit_price=Decimal("500.00"),
                discount=Decimal("50.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("1121.00"),
            )
        ],
    )


def build_customer_payload(business_id: uuid.UUID) -> dict[str, object]:
    """Build a customer create payload."""
    return {
        "business_id": str(business_id),
        "customer_code": "CUST-0001",
        "name": "Aarav Enterprises",
        "email": "billing@example.com",
    }


def build_invoice_payload(
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
) -> dict[str, object]:
    """Build an invoice create payload."""
    return {
        "business_id": str(business_id),
        "customer_id": str(customer_id),
        "invoice_number": "INV-0001",
        "invoice_date": "2026-04-01",
        "subtotal": "0.00",
        "taxable_amount": "0.00",
        "total_amount": "0.00",
        "lines": [
            {
                "description": "Monthly bookkeeping",
                "quantity": "2.00",
                "unit_price": "500.00",
                "discount": "50.00",
                "tax_rate": "18.00",
                "line_total": "0.00",
            }
        ],
    }


def build_client(
    *,
    authenticated: bool = True,
    is_member: bool = True,
) -> tuple[
    TestClient,
    FakeSalesUnitOfWork,
    FakeSalesInvoiceService,
    IdentityUser,
]:
    """Build a test client with Sales dependency overrides."""
    app = create_app(initialize_resources=False)
    business_id = uuid.uuid4()
    customer = build_customer(business_id)
    invoice = build_invoice(business_id, customer.id)
    uow = FakeSalesUnitOfWork(
        customer=customer,
        invoice=invoice,
        is_member=is_member,
    )
    service = FakeSalesInvoiceService(InvoiceResponse.model_validate(invoice))
    user = build_user()

    app.dependency_overrides[get_sales_unit_of_work] = lambda: uow
    app.dependency_overrides[get_sales_invoice_service] = lambda: service
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), uow, service, user


def test_create_customer_endpoint() -> None:
    """Customer create endpoint persists through repository."""
    client, uow, _service, user = build_client()

    with client:
        response = client.post(
            "/api/v1/sales/customers",
            json=build_customer_payload(uow.customers.customer.business_id),
        )

    assert response.status_code == HTTP_CREATED
    assert response.json()["data"]["name"] == "Aarav Enterprises"
    assert uow.committed is True
    assert uow.business_memberships.user_id == user.id


def test_list_customers_endpoint() -> None:
    """Customer list endpoint returns paginated customers."""
    client, uow, _service, _user = build_client()

    with client:
        response = client.get(
            "/api/v1/sales/customers",
            params={"business_id": str(uow.customers.customer.business_id)},
        )

    assert response.status_code == HTTP_OK
    assert response.json()["data"][0]["customer_code"] == "CUST-0001"
    assert response.json()["meta"]["total"] == 1


def test_get_and_update_customer_endpoints() -> None:
    """Customer get and update endpoints work for business members."""
    client, uow, _service, _user = build_client()
    customer_id = uow.customers.customer.id

    with client:
        get_response = client.get(f"/api/v1/sales/customers/{customer_id}")
        patch_response = client.patch(
            f"/api/v1/sales/customers/{customer_id}",
            json={"name": "Aarav Trading"},
        )

    assert get_response.status_code == HTTP_OK
    assert patch_response.status_code == HTTP_OK
    assert patch_response.json()["data"]["name"] == "Aarav Trading"


def test_create_invoice_endpoint() -> None:
    """Invoice create endpoint delegates to service."""
    client, uow, service, _user = build_client()

    with client:
        response = client.post(
            "/api/v1/sales/invoices",
            json=build_invoice_payload(
                uow.customers.customer.business_id,
                uow.customers.customer.id,
            ),
        )

    assert response.status_code == HTTP_CREATED
    assert response.json()["data"]["invoice_number"] == "INV-0001"
    assert service.created_request is not None


def test_list_and_get_invoice_endpoints() -> None:
    """Invoice list and get endpoints return invoice responses."""
    client, uow, _service, _user = build_client()
    invoice_id = uow.sales_invoices.invoice.id

    with client:
        list_response = client.get(
            "/api/v1/sales/invoices",
            params={"business_id": str(uow.sales_invoices.invoice.business_id)},
        )
        get_response = client.get(f"/api/v1/sales/invoices/{invoice_id}")

    assert list_response.status_code == HTTP_OK
    assert list_response.json()["data"][0]["invoice_number"] == "INV-0001"
    assert get_response.status_code == HTTP_OK
    assert get_response.json()["data"]["total_amount"] == "1121.00"


def test_update_issue_and_cancel_invoice_endpoints() -> None:
    """Invoice lifecycle endpoints delegate to service."""
    client, uow, service, _user = build_client()
    invoice_id = uow.sales_invoices.invoice.id

    with client:
        patch_response = client.patch(
            f"/api/v1/sales/invoices/{invoice_id}",
            json={"notes": "Updated"},
        )
        issue_response = client.post(f"/api/v1/sales/invoices/{invoice_id}/issue")
        cancel_response = client.post(f"/api/v1/sales/invoices/{invoice_id}/cancel")

    assert patch_response.status_code == HTTP_OK
    assert patch_response.json()["data"]["notes"] == "Updated"
    assert service.updated_request is not None
    assert issue_response.status_code == HTTP_OK
    assert issue_response.json()["data"]["status"] == "issued"
    assert cancel_response.status_code == HTTP_OK
    assert cancel_response.json()["data"]["status"] == "cancelled"


def test_unauthorized_access() -> None:
    """Sales endpoints require authentication."""
    client, uow, _service, _user = build_client(authenticated=False)

    with client:
        response = client.get(
            "/api/v1/sales/customers",
            params={"business_id": str(uow.customers.customer.business_id)},
        )

    assert response.status_code == HTTP_UNAUTHORIZED
    assert response.json()["data"]["code"] == "authentication.required"


def test_business_isolation() -> None:
    """Non-members cannot access Sales resources."""
    client, uow, _service, _user = build_client(is_member=False)

    with client:
        response = client.get(
            "/api/v1/sales/customers",
            params={"business_id": str(uow.customers.customer.business_id)},
        )

    assert response.status_code == HTTP_FORBIDDEN
    assert response.json()["data"]["code"] == "business.not_member"


def test_openapi_documents_sales_routes() -> None:
    """OpenAPI includes Sales route documentation."""
    client, _uow, _service, _user = build_client()

    with client:
        schema = client.get("/openapi.json").json()

    assert "/api/v1/sales/customers" in schema["paths"]
    assert "/api/v1/sales/invoices" in schema["paths"]
    assert "/api/v1/sales/invoices/{invoice_id}/issue" in schema["paths"]
    assert schema["paths"]["/api/v1/sales/customers"]["post"]["summary"] == (
        "Create customer"
    )
    assert schema["paths"]["/api/v1/sales/invoices"]["post"]["summary"] == (
        "Create invoice"
    )
