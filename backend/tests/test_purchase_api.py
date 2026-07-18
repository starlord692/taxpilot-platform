"""Tests for Purchase Management API routers."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.common.pagination import Page, PaginationParams
from app.main import create_app
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus
from app.modules.purchases.api.dependencies import (
    get_purchase_service,
    get_purchase_unit_of_work,
    get_supplier_service,
)
from app.modules.purchases.models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchaseStatus,
    Supplier,
)
from app.modules.purchases.schemas import (
    PurchaseInvoiceCreate,
    PurchaseInvoiceResponse,
    PurchaseInvoiceUpdate,
    SupplierCreate,
    SupplierListResponse,
    SupplierResponse,
    SupplierUpdate,
)

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


class FakeSupplierRepository:
    """Fake supplier repository."""

    def __init__(self, supplier: Supplier) -> None:
        """Initialize with a supplier."""
        self.supplier = supplier

    async def get_by_id(self, supplier_id: uuid.UUID) -> Supplier | None:
        """Return supplier by id."""
        if self.supplier.id == supplier_id:
            return self.supplier
        return None


class FakePurchaseRepository:
    """Fake purchase repository."""

    def __init__(self, purchase: PurchaseInvoice) -> None:
        """Initialize with a purchase invoice."""
        self.purchase = purchase

    async def get_by_id(self, purchase_id: uuid.UUID) -> PurchaseInvoice | None:
        """Return purchase by id."""
        if self.purchase.id == purchase_id:
            return self.purchase
        return None


class FakePurchaseUnitOfWork:
    """Fake Purchase Unit of Work for API tests."""

    def __init__(
        self,
        *,
        supplier: Supplier,
        purchase: PurchaseInvoice,
        is_member: bool = True,
    ) -> None:
        """Initialize fake repositories."""
        self.suppliers = FakeSupplierRepository(supplier)
        self.purchase_invoices = FakePurchaseRepository(purchase)
        self.business_memberships = FakeMembershipRepository(is_member=is_member)

    async def __aenter__(self) -> "FakePurchaseUnitOfWork":
        """Enter fake transaction scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit fake transaction scope."""


class FakeSupplierService:
    """Fake supplier service for API tests."""

    def __init__(self, supplier: SupplierResponse) -> None:
        """Initialize with a supplier response."""
        self.supplier = supplier
        self.created_request: SupplierCreate | None = None
        self.updated_request: SupplierUpdate | None = None
        self.deactivated_supplier_id: uuid.UUID | None = None
        self.reactivated_supplier_id: uuid.UUID | None = None
        self.business_id: uuid.UUID | None = None
        self.pagination: PaginationParams | None = None
        self.search: str | None = None

    async def create_supplier(
        self,
        request: SupplierCreate,
        *,
        business_id: uuid.UUID,
    ) -> SupplierResponse:
        """Return created supplier."""
        self.created_request = request
        self.business_id = business_id
        return self.supplier

    async def update_supplier(
        self,
        supplier_id: uuid.UUID,
        request: SupplierUpdate,
    ) -> SupplierResponse:
        """Return updated supplier."""
        _ = supplier_id
        self.updated_request = request
        return self.supplier.model_copy(update=request.model_dump(exclude_unset=True))

    async def deactivate_supplier(self, supplier_id: uuid.UUID) -> SupplierResponse:
        """Record supplier deactivation."""
        self.deactivated_supplier_id = supplier_id
        return self.supplier.model_copy(update={"is_active": False})

    async def reactivate_supplier(self, supplier_id: uuid.UUID) -> SupplierResponse:
        """Record supplier reactivation."""
        self.reactivated_supplier_id = supplier_id
        return self.supplier.model_copy(update={"is_active": True})

    async def get_supplier(self, supplier_id: uuid.UUID) -> SupplierResponse:
        """Return supplier."""
        _ = supplier_id
        return self.supplier

    async def list_suppliers(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        sort: str | None = None,
        search: str | None = None,
    ) -> Page[SupplierListResponse]:
        """Return supplier page."""
        _ = sort
        self.business_id = business_id
        self.pagination = pagination or PaginationParams()
        self.search = search
        return Page.create(
            items=[SupplierListResponse.model_validate(self.supplier)],
            total=1,
            params=self.pagination,
        )


class FakePurchaseService:
    """Fake purchase service for API tests."""

    def __init__(self, purchase: PurchaseInvoiceResponse) -> None:
        """Initialize with a purchase response."""
        self.purchase = purchase
        self.created_request: PurchaseInvoiceCreate | None = None
        self.updated_request: PurchaseInvoiceUpdate | None = None
        self.business_id: uuid.UUID | None = None
        self.pagination: PaginationParams | None = None
        self.search: str | None = None
        self.approved_purchase_id: uuid.UUID | None = None
        self.received_purchase_id: uuid.UUID | None = None
        self.paid_purchase_id: uuid.UUID | None = None
        self.cancelled_purchase_id: uuid.UUID | None = None

    async def create_purchase(
        self,
        request: PurchaseInvoiceCreate,
        *,
        business_id: uuid.UUID,
    ) -> PurchaseInvoiceResponse:
        """Return created purchase."""
        self.created_request = request
        self.business_id = business_id
        return self.purchase

    async def update_purchase(
        self,
        purchase_id: uuid.UUID,
        request: PurchaseInvoiceUpdate,
    ) -> PurchaseInvoiceResponse:
        """Return updated purchase."""
        _ = purchase_id
        self.updated_request = request
        return self.purchase.model_copy(update=request.model_dump(exclude_unset=True))

    async def approve_purchase(self, purchase_id: uuid.UUID) -> PurchaseInvoiceResponse:
        """Return approved purchase."""
        self.approved_purchase_id = purchase_id
        return self.purchase.model_copy(update={"status": PurchaseStatus.APPROVED})

    async def mark_received(self, purchase_id: uuid.UUID) -> PurchaseInvoiceResponse:
        """Return received purchase."""
        self.received_purchase_id = purchase_id
        return self.purchase.model_copy(update={"status": PurchaseStatus.RECEIVED})

    async def mark_paid(self, purchase_id: uuid.UUID) -> PurchaseInvoiceResponse:
        """Return paid purchase."""
        self.paid_purchase_id = purchase_id
        return self.purchase.model_copy(update={"status": PurchaseStatus.PAID})

    async def cancel_purchase(self, purchase_id: uuid.UUID) -> PurchaseInvoiceResponse:
        """Return cancelled purchase."""
        self.cancelled_purchase_id = purchase_id
        return self.purchase.model_copy(update={"status": PurchaseStatus.CANCELLED})

    async def get_purchase(self, purchase_id: uuid.UUID) -> PurchaseInvoiceResponse:
        """Return purchase."""
        _ = purchase_id
        return self.purchase

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
        """Return purchase page."""
        _ = sort
        _ = supplier_id
        _ = status
        _ = invoice_date_from
        _ = invoice_date_to
        _ = due_date_from
        _ = due_date_to
        _ = purchase_number
        _ = invoice_number
        self.business_id = business_id
        self.pagination = pagination or PaginationParams()
        self.search = search
        return Page.create(items=[self.purchase], total=1, params=self.pagination)


def build_user() -> IdentityUser:
    """Build an authenticated identity user."""
    return IdentityUser(
        id=uuid.uuid4(),
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=UserStatus.ACTIVE,
        failed_login_attempts=0,
    )


def build_supplier(business_id: uuid.UUID) -> Supplier:
    """Build a supplier model."""
    return Supplier(
        id=uuid.uuid4(),
        business_id=business_id,
        supplier_code="SUP-0001",
        name="Aarav Wholesale",
        email="billing@example.com",
        gstin="29ABCDE1234F1Z5",
        is_active=True,
    )


def build_purchase(business_id: uuid.UUID, supplier_id: uuid.UUID) -> PurchaseInvoice:
    """Build a purchase invoice model."""
    purchase_id = uuid.uuid4()
    return PurchaseInvoice(
        id=purchase_id,
        business_id=business_id,
        supplier_id=supplier_id,
        purchase_number="PUR-0001",
        invoice_number="SUP-INV-0001",
        invoice_date=date(2026, 6, 1),
        status=PurchaseStatus.DRAFT,
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        attachment_count=1,
        lines=[
            PurchaseInvoiceLine(
                id=uuid.uuid4(),
                purchase_invoice_id=purchase_id,
                description="Office laptops",
                quantity=Decimal("2.00"),
                unit_cost=Decimal("500.00"),
                tax_rate=Decimal("18.00"),
                line_total=Decimal("1180.00"),
            )
        ],
    )


def build_supplier_payload() -> dict[str, object]:
    """Build supplier request payload."""
    return {
        "name": "Aarav Wholesale",
        "email": "billing@example.com",
        "phone": "+919876543210",
        "gstin": "29ABCDE1234F1Z5",
        "pan": "ABCDE1234F",
        "address": "Bengaluru",
        "payment_terms": "Net 30",
    }


def build_purchase_payload(supplier_id: uuid.UUID) -> dict[str, object]:
    """Build purchase request payload."""
    return {
        "supplier_id": str(supplier_id),
        "invoice_number": "SUP-INV-0001",
        "invoice_date": "2026-06-01",
        "due_date": "2026-06-30",
        "subtotal": "1000.00",
        "tax_amount": "180.00",
        "total_amount": "1180.00",
        "attachment_count": 1,
        "lines": [
            {
                "description": "Office laptops",
                "quantity": "2.00",
                "unit_cost": "500.00",
                "tax_rate": "18.00",
                "line_total": "1180.00",
            }
        ],
    }


def build_client(
    *,
    authenticated: bool = True,
    is_member: bool = True,
) -> tuple[
    TestClient,
    FakePurchaseUnitOfWork,
    FakeSupplierService,
    FakePurchaseService,
    IdentityUser,
]:
    """Build a test client with purchase dependency overrides."""
    app = create_app(initialize_resources=False)
    business_id = uuid.uuid4()
    supplier = build_supplier(business_id)
    purchase = build_purchase(business_id, supplier.id)
    uow = FakePurchaseUnitOfWork(
        supplier=supplier,
        purchase=purchase,
        is_member=is_member,
    )
    supplier_service = FakeSupplierService(SupplierResponse.model_validate(supplier))
    purchase_service = FakePurchaseService(
        PurchaseInvoiceResponse.model_validate(purchase)
    )
    user = build_user()

    app.dependency_overrides[get_purchase_unit_of_work] = lambda: uow
    app.dependency_overrides[get_supplier_service] = lambda: supplier_service
    app.dependency_overrides[get_purchase_service] = lambda: purchase_service
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), uow, supplier_service, purchase_service, user


def test_supplier_endpoints() -> None:
    """Supplier endpoints delegate to service and enforce membership."""
    client, uow, supplier_service, _purchase_service, _user = build_client()

    with client:
        create_response = client.post(
            "/api/v1/purchases/suppliers",
            params={"business_id": str(uow.suppliers.supplier.business_id)},
            json=build_supplier_payload(),
        )
        list_response = client.get(
            "/api/v1/purchases/suppliers",
            params={
                "business_id": str(uow.suppliers.supplier.business_id),
                "page": 1,
                "page_size": 10,
                "search": "Aarav",
            },
        )
        get_response = client.get(
            f"/api/v1/purchases/suppliers/{uow.suppliers.supplier.id}"
        )
        patch_response = client.patch(
            f"/api/v1/purchases/suppliers/{uow.suppliers.supplier.id}",
            json={"name": "Aarav Trading"},
        )
        delete_response = client.delete(
            f"/api/v1/purchases/suppliers/{uow.suppliers.supplier.id}"
        )
        reactivate_response = client.post(
            f"/api/v1/purchases/suppliers/{uow.suppliers.supplier.id}/reactivate"
        )

    assert create_response.status_code == HTTP_CREATED
    assert list_response.status_code == HTTP_OK
    assert list_response.json()["meta"]["total"] == 1
    assert get_response.status_code == HTTP_OK
    assert patch_response.status_code == HTTP_OK
    assert patch_response.json()["data"]["name"] == "Aarav Trading"
    assert delete_response.status_code == HTTP_NO_CONTENT
    assert reactivate_response.status_code == HTTP_OK
    assert supplier_service.created_request is not None
    assert supplier_service.updated_request is not None
    assert supplier_service.deactivated_supplier_id == uow.suppliers.supplier.id
    assert supplier_service.reactivated_supplier_id == uow.suppliers.supplier.id
    assert supplier_service.search == "Aarav"


def test_purchase_endpoints_and_status_transitions() -> None:
    """Purchase endpoints delegate CRUD and lifecycle actions to service."""
    client, uow, _supplier_service, purchase_service, _user = build_client()

    with client:
        create_response = client.post(
            "/api/v1/purchases",
            params={"business_id": str(uow.purchase_invoices.purchase.business_id)},
            json=build_purchase_payload(uow.suppliers.supplier.id),
        )
        list_response = client.get(
            "/api/v1/purchases",
            params={
                "business_id": str(uow.purchase_invoices.purchase.business_id),
                "page": 1,
                "page_size": 10,
                "status": "draft",
                "supplier": str(uow.suppliers.supplier.id),
                "search": "SUP-INV",
            },
        )
        get_response = client.get(
            f"/api/v1/purchases/{uow.purchase_invoices.purchase.id}"
        )
        patch_response = client.patch(
            f"/api/v1/purchases/{uow.purchase_invoices.purchase.id}",
            json={"notes": "Updated"},
        )
        approve_response = client.post(
            f"/api/v1/purchases/{uow.purchase_invoices.purchase.id}/approve"
        )
        receive_response = client.post(
            f"/api/v1/purchases/{uow.purchase_invoices.purchase.id}/receive"
        )
        pay_response = client.post(
            f"/api/v1/purchases/{uow.purchase_invoices.purchase.id}/pay"
        )
        cancel_response = client.post(
            f"/api/v1/purchases/{uow.purchase_invoices.purchase.id}/cancel"
        )

    assert create_response.status_code == HTTP_CREATED
    assert list_response.status_code == HTTP_OK
    assert list_response.json()["meta"]["total"] == 1
    assert get_response.status_code == HTTP_OK
    assert patch_response.status_code == HTTP_OK
    assert patch_response.json()["data"]["notes"] == "Updated"
    assert approve_response.status_code == HTTP_OK
    assert approve_response.json()["data"]["status"] == "approved"
    assert receive_response.status_code == HTTP_OK
    assert receive_response.json()["data"]["status"] == "received"
    assert pay_response.status_code == HTTP_OK
    assert pay_response.json()["data"]["status"] == "paid"
    assert cancel_response.status_code == HTTP_OK
    assert cancel_response.json()["data"]["status"] == "cancelled"
    assert purchase_service.created_request is not None
    assert purchase_service.updated_request is not None
    assert purchase_service.search == "SUP-INV"
    assert purchase_service.approved_purchase_id == uow.purchase_invoices.purchase.id
    assert purchase_service.received_purchase_id == uow.purchase_invoices.purchase.id
    assert purchase_service.paid_purchase_id == uow.purchase_invoices.purchase.id
    assert purchase_service.cancelled_purchase_id == uow.purchase_invoices.purchase.id


def test_purchase_api_requires_authentication() -> None:
    """Purchase endpoints require authentication."""
    client, uow, _supplier_service, _purchase_service, _user = build_client(
        authenticated=False
    )

    with client:
        response = client.get(
            f"/api/v1/purchases/suppliers/{uow.suppliers.supplier.id}"
        )

    assert response.status_code == HTTP_UNAUTHORIZED
    assert response.json()["data"]["code"] == "authentication.required"


def test_purchase_api_business_isolation() -> None:
    """Non-members cannot access purchase resources."""
    client, uow, _supplier_service, _purchase_service, _user = build_client(
        is_member=False
    )

    with client:
        response = client.get(
            f"/api/v1/purchases/{uow.purchase_invoices.purchase.id}"
        )

    assert response.status_code == HTTP_FORBIDDEN
    assert response.json()["data"]["code"] == "business.not_member"


def test_openapi_documents_purchase_routes() -> None:
    """OpenAPI includes purchase route documentation."""
    client, _uow, _supplier_service, _purchase_service, _user = build_client()

    with client:
        schema = client.get("/openapi.json").json()

    assert "/api/v1/purchases/suppliers" in schema["paths"]
    assert "/api/v1/purchases/suppliers/{supplier_id}" in schema["paths"]
    assert "/api/v1/purchases" in schema["paths"]
    assert "/api/v1/purchases/{purchase_id}/approve" in schema["paths"]
    assert schema["paths"]["/api/v1/purchases/suppliers"]["post"]["summary"] == (
        "Create supplier"
    )
    assert schema["paths"]["/api/v1/purchases"]["post"]["summary"] == (
        "Create purchase"
    )
