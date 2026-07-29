"""Tests for Expense Management API routers."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.common.pagination import Page, PaginationParams
from app.main import create_app
from app.modules.business.models import BusinessMembership
from app.modules.expenses.api.dependencies import (
    get_expense_service,
    get_expense_unit_of_work,
    get_vendor_service,
)
from app.modules.expenses.models import Expense, ExpenseCategory, ExpenseStatus, Vendor
from app.modules.expenses.schemas import (
    ExpenseCreate,
    ExpenseResponse,
    ExpenseUpdate,
    VendorCreate,
    VendorListResponse,
    VendorResponse,
    VendorUpdate,
)
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus
from tests.support.business_context import FakeBusinessRepository

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

    async def get_membership(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> BusinessMembership | None:
        """Return configured active membership result."""
        if not self.member:
            return None
        return BusinessMembership(
            id=uuid.uuid4(),
            business_id=business_id,
            user_id=user_id,
            role="member",
        )


class FakeVendorRepository:
    """Fake vendor repository."""

    def __init__(self, vendor: Vendor) -> None:
        """Initialize with a vendor."""
        self.vendor = vendor

    async def get_by_id(self, vendor_id: uuid.UUID) -> Vendor | None:
        """Return vendor by id."""
        if self.vendor.id == vendor_id:
            return self.vendor
        return None


class FakeExpenseRepository:
    """Fake expense repository."""

    def __init__(self, expense: Expense) -> None:
        """Initialize with an expense."""
        self.expense = expense

    async def get_by_id(self, expense_id: uuid.UUID) -> Expense | None:
        """Return expense by id."""
        if self.expense.id == expense_id:
            return self.expense
        return None


class FakeExpenseUnitOfWork:
    """Fake Expense Unit of Work for API tests."""

    def __init__(
        self,
        *,
        vendor: Vendor,
        expense: Expense,
        is_member: bool = True,
    ) -> None:
        """Initialize fake repositories."""
        self.vendors = FakeVendorRepository(vendor)
        self.expenses = FakeExpenseRepository(expense)
        self.businesses = FakeBusinessRepository()
        self.business_memberships = FakeMembershipRepository(is_member=is_member)

    async def __aenter__(self) -> "FakeExpenseUnitOfWork":
        """Enter fake transaction scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Exit fake transaction scope."""


class FakeVendorService:
    """Fake vendor service for API tests."""

    def __init__(self, vendor: VendorResponse) -> None:
        """Initialize with a vendor response."""
        self.vendor = vendor
        self.created_request: VendorCreate | None = None
        self.updated_request: VendorUpdate | None = None
        self.deactivated_vendor_id: uuid.UUID | None = None
        self.business_id: uuid.UUID | None = None
        self.pagination: PaginationParams | None = None

    async def create_vendor(
        self,
        request: VendorCreate,
        *,
        business_id: uuid.UUID,
    ) -> VendorResponse:
        """Return created vendor."""
        self.created_request = request
        self.business_id = business_id
        return self.vendor

    async def update_vendor(
        self,
        vendor_id: uuid.UUID,
        request: VendorUpdate,
    ) -> VendorResponse:
        """Return updated vendor."""
        _ = vendor_id
        self.updated_request = request
        return self.vendor.model_copy(update=request.model_dump(exclude_unset=True))

    async def deactivate_vendor(self, vendor_id: uuid.UUID) -> VendorResponse:
        """Record deactivation."""
        self.deactivated_vendor_id = vendor_id
        return self.vendor.model_copy(update={"is_active": False})

    async def get_vendor(self, vendor_id: uuid.UUID) -> VendorResponse:
        """Return vendor."""
        _ = vendor_id
        return self.vendor

    async def list_vendors(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        sort: str | None = None,
    ) -> Page[VendorListResponse]:
        """Return vendor page."""
        _ = sort
        self.business_id = business_id
        params = pagination or PaginationParams()
        self.pagination = params
        return Page.create(
            items=[VendorListResponse.model_validate(self.vendor)],
            total=1,
            params=params,
        )


class FakeExpenseService:
    """Fake expense service for API tests."""

    def __init__(self, expense: ExpenseResponse) -> None:
        """Initialize with an expense response."""
        self.expense = expense
        self.created_request: ExpenseCreate | None = None
        self.updated_request: ExpenseUpdate | None = None
        self.business_id: uuid.UUID | None = None
        self.pagination: PaginationParams | None = None
        self.approved_expense_id: uuid.UUID | None = None
        self.paid_expense_id: uuid.UUID | None = None
        self.cancelled_expense_id: uuid.UUID | None = None

    async def create_expense(
        self,
        request: ExpenseCreate,
        *,
        business_id: uuid.UUID,
    ) -> ExpenseResponse:
        """Return created expense."""
        self.created_request = request
        self.business_id = business_id
        return self.expense

    async def update_expense(
        self,
        expense_id: uuid.UUID,
        request: ExpenseUpdate,
    ) -> ExpenseResponse:
        """Return updated expense."""
        _ = expense_id
        self.updated_request = request
        return self.expense.model_copy(update=request.model_dump(exclude_unset=True))

    async def approve_expense(self, expense_id: uuid.UUID) -> ExpenseResponse:
        """Return approved expense."""
        self.approved_expense_id = expense_id
        return self.expense.model_copy(update={"status": ExpenseStatus.APPROVED})

    async def mark_paid(self, expense_id: uuid.UUID) -> ExpenseResponse:
        """Return paid expense."""
        self.paid_expense_id = expense_id
        return self.expense.model_copy(update={"status": ExpenseStatus.PAID})

    async def cancel_expense(self, expense_id: uuid.UUID) -> ExpenseResponse:
        """Return cancelled expense."""
        self.cancelled_expense_id = expense_id
        return self.expense.model_copy(update={"status": ExpenseStatus.CANCELLED})

    async def get_expense(self, expense_id: uuid.UUID) -> ExpenseResponse:
        """Return expense."""
        _ = expense_id
        return self.expense

    async def list_expenses(
        self,
        business_id: uuid.UUID,
        pagination: PaginationParams | None = None,
        *,
        sort: str | None = None,
        vendor_id: uuid.UUID | None = None,
        status: ExpenseStatus | None = None,
        expense_date_from: date | None = None,
        expense_date_to: date | None = None,
    ) -> Page[ExpenseResponse]:
        """Return expense page."""
        _ = sort
        _ = vendor_id
        _ = status
        _ = expense_date_from
        _ = expense_date_to
        self.business_id = business_id
        params = pagination or PaginationParams()
        self.pagination = params
        return Page.create(items=[self.expense], total=1, params=params)


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


def build_vendor(business_id: uuid.UUID) -> Vendor:
    """Build a vendor model."""
    return Vendor(
        id=uuid.uuid4(),
        business_id=business_id,
        vendor_code="VEND-0001",
        name="Aarav Supplies",
        email="billing@example.com",
        is_active=True,
    )


def build_expense(business_id: uuid.UUID, vendor_id: uuid.UUID) -> Expense:
    """Build an expense model."""
    return Expense(
        id=uuid.uuid4(),
        business_id=business_id,
        vendor_id=vendor_id,
        expense_number="EXP-0001",
        expense_date=date(2026, 5, 1),
        category=ExpenseCategory.SOFTWARE,
        description="Accounting software",
        status=ExpenseStatus.DRAFT,
        subtotal=Decimal("1000.00"),
        tax_amount=Decimal("180.00"),
        total_amount=Decimal("1180.00"),
        attachment_count=1,
    )


def build_vendor_payload() -> dict[str, object]:
    """Build vendor request payload."""
    return {
        "name": "Aarav Supplies",
        "email": "billing@example.com",
        "phone": "+919876543210",
        "gstin": "29ABCDE1234F1Z5",
        "pan": "ABCDE1234F",
        "address": "Bengaluru",
    }


def build_expense_payload(vendor_id: uuid.UUID) -> dict[str, object]:
    """Build expense request payload."""
    return {
        "vendor_id": str(vendor_id),
        "expense_date": "2026-05-01",
        "category": "software",
        "description": "Accounting software",
        "subtotal": "1000.00",
        "tax_amount": "180.00",
        "total_amount": "1180.00",
        "attachment_count": 1,
        "lines": [
            {
                "description": "Cloud hosting",
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
    FakeExpenseUnitOfWork,
    FakeVendorService,
    FakeExpenseService,
    IdentityUser,
]:
    """Build a test client with expense dependency overrides."""
    app = create_app(initialize_resources=False)
    business_id = uuid.uuid4()
    vendor = build_vendor(business_id)
    expense = build_expense(business_id, vendor.id)
    uow = FakeExpenseUnitOfWork(
        vendor=vendor,
        expense=expense,
        is_member=is_member,
    )
    vendor_service = FakeVendorService(VendorResponse.model_validate(vendor))
    expense_service = FakeExpenseService(ExpenseResponse.model_validate(expense))
    user = build_user()

    app.dependency_overrides[get_expense_unit_of_work] = lambda: uow
    app.dependency_overrides[get_vendor_service] = lambda: vendor_service
    app.dependency_overrides[get_expense_service] = lambda: expense_service
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), uow, vendor_service, expense_service, user


def test_vendor_crud_api() -> None:
    """Vendor endpoints delegate to service and enforce membership."""
    client, uow, vendor_service, _expense_service, _user = build_client()

    with client:
        create_response = client.post(
            "/api/v1/expenses/vendors",
            params={"business_id": str(uow.vendors.vendor.business_id)},
            json=build_vendor_payload(),
        )
        list_response = client.get(
            "/api/v1/expenses/vendors",
            params={
                "business_id": str(uow.vendors.vendor.business_id),
                "page": 1,
                "page_size": 10,
            },
        )
        get_response = client.get(f"/api/v1/expenses/vendors/{uow.vendors.vendor.id}")
        patch_response = client.patch(
            f"/api/v1/expenses/vendors/{uow.vendors.vendor.id}",
            json={"name": "Aarav Trading"},
        )
        delete_response = client.delete(
            f"/api/v1/expenses/vendors/{uow.vendors.vendor.id}"
        )

    assert create_response.status_code == HTTP_CREATED
    assert list_response.status_code == HTTP_OK
    assert list_response.json()["meta"]["total"] == 1
    assert get_response.status_code == HTTP_OK
    assert patch_response.status_code == HTTP_OK
    assert patch_response.json()["data"]["name"] == "Aarav Trading"
    assert delete_response.status_code == HTTP_NO_CONTENT
    assert vendor_service.created_request is not None
    assert vendor_service.updated_request is not None
    assert vendor_service.deactivated_vendor_id == uow.vendors.vendor.id


def test_expense_crud_and_lifecycle_api() -> None:
    """Expense endpoints delegate CRUD and lifecycle actions to service."""
    client, uow, _vendor_service, expense_service, _user = build_client()

    with client:
        create_response = client.post(
            "/api/v1/expenses",
            params={"business_id": str(uow.expenses.expense.business_id)},
            json=build_expense_payload(uow.vendors.vendor.id),
        )
        list_response = client.get(
            "/api/v1/expenses",
            params={
                "business_id": str(uow.expenses.expense.business_id),
                "page": 1,
                "page_size": 10,
                "status": "draft",
            },
        )
        get_response = client.get(f"/api/v1/expenses/{uow.expenses.expense.id}")
        patch_response = client.patch(
            f"/api/v1/expenses/{uow.expenses.expense.id}",
            json={"notes": "Updated"},
        )
        approve_response = client.post(
            f"/api/v1/expenses/{uow.expenses.expense.id}/approve"
        )
        pay_response = client.post(f"/api/v1/expenses/{uow.expenses.expense.id}/pay")
        cancel_response = client.post(
            f"/api/v1/expenses/{uow.expenses.expense.id}/cancel"
        )

    assert create_response.status_code == HTTP_CREATED
    assert list_response.status_code == HTTP_OK
    assert list_response.json()["meta"]["total"] == 1
    assert get_response.status_code == HTTP_OK
    assert patch_response.status_code == HTTP_OK
    assert patch_response.json()["data"]["notes"] == "Updated"
    assert approve_response.status_code == HTTP_OK
    assert approve_response.json()["data"]["status"] == "approved"
    assert pay_response.status_code == HTTP_OK
    assert pay_response.json()["data"]["status"] == "paid"
    assert cancel_response.status_code == HTTP_OK
    assert cancel_response.json()["data"]["status"] == "cancelled"
    assert expense_service.created_request is not None
    assert expense_service.updated_request is not None
    assert expense_service.approved_expense_id == uow.expenses.expense.id
    assert expense_service.paid_expense_id == uow.expenses.expense.id
    assert expense_service.cancelled_expense_id == uow.expenses.expense.id


def test_expense_api_requires_authentication() -> None:
    """Expense endpoints require authentication."""
    client, uow, _vendor_service, _expense_service, _user = build_client(
        authenticated=False
    )

    with client:
        response = client.get(f"/api/v1/expenses/{uow.expenses.expense.id}")

    assert response.status_code == HTTP_UNAUTHORIZED
    assert response.json()["data"]["code"] == "authentication.required"


def test_expense_api_business_isolation() -> None:
    """Non-members cannot access expense resources."""
    client, uow, _vendor_service, _expense_service, _user = build_client(
        is_member=False
    )

    with client:
        response = client.get(f"/api/v1/expenses/{uow.expenses.expense.id}")

    assert response.status_code == HTTP_FORBIDDEN
    assert response.json()["data"]["code"] == "business.not_member"


def test_openapi_documents_expense_routes() -> None:
    """OpenAPI includes expense route documentation."""
    client, _uow, _vendor_service, _expense_service, _user = build_client()

    with client:
        schema = client.get("/openapi.json").json()

    assert "/api/v1/expenses/vendors" in schema["paths"]
    assert "/api/v1/expenses/vendors/{vendor_id}" in schema["paths"]
    assert "/api/v1/expenses" in schema["paths"]
    assert "/api/v1/expenses/{expense_id}/approve" in schema["paths"]
    assert schema["paths"]["/api/v1/expenses/vendors"]["post"]["summary"] == (
        "Create vendor"
    )
    assert schema["paths"]["/api/v1/expenses"]["post"]["summary"] == (
        "Create expense"
    )
