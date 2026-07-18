"""Tests for business API router."""

import uuid
from datetime import date

from fastapi.testclient import TestClient

from app.common.pagination import Page, PaginationParams
from app.main import create_app
from app.modules.business.api.dependencies import get_business_service
from app.modules.business.exceptions import (
    BusinessDuplicateNameException,
    BusinessNotMemberException,
)
from app.modules.business.models import (
    Business,
    BusinessAddress,
    BusinessSettings,
    BusinessStatus,
    BusinessTaxProfile,
    BusinessType,
    RegistrationStatus,
)
from app.modules.business.schemas import (
    BusinessResponse,
    BusinessSummaryResponse,
    CreateBusinessRequest,
    UpdateBusinessRequest,
)
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus

HTTP_CREATED = 201
HTTP_FORBIDDEN = 403
HTTP_NO_CONTENT = 204
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_CONFLICT = 409


class FakeBusinessService:
    """Fake business service for API tests."""

    def __init__(self, *, error: Exception | None = None) -> None:
        """Initialize fake behavior."""
        self.error = error
        self.created_request: CreateBusinessRequest | None = None
        self.updated_request: UpdateBusinessRequest | None = None
        self.owner_user_id: uuid.UUID | None = None
        self.user_id: uuid.UUID | None = None
        self.business_code: str | None = None
        self.pagination: PaginationParams | None = None
        self.search: str | None = None
        self.sort: str | None = None
        self.archived = False
        self.business = build_business_response()

    async def create_business(
        self,
        request: CreateBusinessRequest,
        owner_user_id: uuid.UUID,
    ) -> BusinessResponse:
        """Return a created business or raise configured error."""
        self.created_request = request
        self.owner_user_id = owner_user_id
        if self.error is not None:
            raise self.error
        return self.business

    async def list_businesses(
        self,
        user_id: uuid.UUID,
        pagination: PaginationParams,
        *,
        search: str | None = None,
        sort: str | None = None,
    ) -> Page[BusinessSummaryResponse]:
        """Return paginated business summaries."""
        self.user_id = user_id
        self.pagination = pagination
        self.search = search
        self.sort = sort
        summary = BusinessSummaryResponse.model_validate(
            Business(
                id=self.business.id,
                legal_name=self.business.legal_name,
                trade_name=self.business.trade_name,
                business_type=self.business.business_type,
                status=self.business.status,
            )
        )
        return Page.create(items=[summary], total=1, params=pagination)

    async def get_business(
        self,
        business_code: str,
        user_id: uuid.UUID,
    ) -> BusinessResponse:
        """Return a business by code or raise configured error."""
        self.business_code = business_code
        self.user_id = user_id
        if self.error is not None:
            raise self.error
        return self.business

    async def update_business_by_code(
        self,
        business_code: str,
        request: UpdateBusinessRequest,
        user_id: uuid.UUID,
    ) -> BusinessResponse:
        """Return an updated business by code or raise configured error."""
        self.business_code = business_code
        self.updated_request = request
        self.user_id = user_id
        if self.error is not None:
            raise self.error
        return self.business.model_copy(update={"trade_name": request.trade_name})

    async def archive_business_by_code(
        self,
        business_code: str,
        user_id: uuid.UUID,
    ) -> None:
        """Archive a business by code or raise configured error."""
        self.business_code = business_code
        self.user_id = user_id
        if self.error is not None:
            raise self.error
        self.archived = True


def build_business_payload() -> dict[str, object]:
    """Build a valid create business payload."""
    return {
        "legal_name": "TaxPilot Labs Private Limited",
        "trade_name": "TaxPilot Labs",
        "business_type": "private_limited",
        "registration_status": "registered",
        "business_email": "accounts@example.com",
        "business_phone": "+919876543210",
        "website": "https://example.com",
        "address": {
            "address_line_1": "42 Residency Road",
            "city": "Bengaluru",
            "state": "Karnataka",
            "country": "India",
            "postal_code": "560025",
        },
        "tax_profile": {
            "gstin": "29ABCDE1234F1Z5",
            "pan": "ABCDE1234F",
            "financial_year_start": "2026-04-01",
        },
        "settings": {
            "currency": "INR",
            "timezone": "Asia/Kolkata",
            "language": "en",
        },
    }


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


def build_business_response() -> BusinessResponse:
    """Build a business response from ORM attributes."""
    business_id = uuid.uuid4()
    business = Business(
        id=business_id,
        legal_name="TaxPilot Labs Private Limited",
        trade_name="TaxPilot Labs",
        business_type=BusinessType.PRIVATE_LIMITED,
        registration_status=RegistrationStatus.REGISTERED,
        business_email="accounts@example.com",
        business_phone="+919876543210",
        website="https://example.com",
        status=BusinessStatus.ACTIVE,
        address=BusinessAddress(
            id=uuid.uuid4(),
            business_id=business_id,
            address_line_1="42 Residency Road",
            city="Bengaluru",
            state="Karnataka",
            country="India",
            postal_code="560025",
        ),
        tax_profile=BusinessTaxProfile(
            id=uuid.uuid4(),
            business_id=business_id,
            gstin="29ABCDE1234F1Z5",
            pan="ABCDE1234F",
            financial_year_start=date(2026, 4, 1),
            gst_registered=True,
            composition_scheme=False,
        ),
        settings=BusinessSettings(
            id=uuid.uuid4(),
            business_id=business_id,
            currency="INR",
            timezone="Asia/Kolkata",
            date_format="DD/MM/YYYY",
            language="en",
        ),
    )
    return BusinessResponse.model_validate(business)


def build_client(
    service: FakeBusinessService,
    *,
    authenticated: bool = True,
) -> tuple[TestClient, IdentityUser]:
    """Build a test client with business service and auth overrides."""
    app = create_app(initialize_resources=False)
    user = build_user()
    app.dependency_overrides[get_business_service] = lambda: service
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), user


def test_create_business() -> None:
    """Create business endpoint delegates to service."""
    service = FakeBusinessService()
    client, user = build_client(service)

    with client:
        response = client.post("/api/v1/businesses/", json=build_business_payload())

    assert response.status_code == HTTP_CREATED
    assert response.json()["success"] is True
    assert response.json()["data"]["legal_name"] == "TaxPilot Labs Private Limited"
    assert service.owner_user_id == user.id
    assert service.created_request is not None


def test_duplicate_business_returns_conflict() -> None:
    """Duplicate business errors are returned as 409."""
    service = FakeBusinessService(
        error=BusinessDuplicateNameException("Business name already exists")
    )
    client, _user = build_client(service)

    with client:
        response = client.post("/api/v1/businesses/", json=build_business_payload())

    assert response.status_code == HTTP_CONFLICT
    assert response.json()["data"]["code"] == "business.duplicate_name"


def test_list_businesses() -> None:
    """List endpoint returns paginated business summaries."""
    service = FakeBusinessService()
    client, user = build_client(service)

    with client:
        response = client.get(
            "/api/v1/businesses/",
            params={"page": 1, "page_size": 10, "search": "Tax", "sort": "legal_name"},
        )

    payload = response.json()
    assert response.status_code == HTTP_OK
    assert payload["success"] is True
    assert payload["data"][0]["legal_name"] == "TaxPilot Labs Private Limited"
    assert payload["meta"]["total"] == 1
    assert service.user_id == user.id
    assert service.pagination == PaginationParams(page=1, size=10)
    assert service.search == "Tax"
    assert service.sort == "legal_name"


def test_get_business() -> None:
    """Get endpoint returns a business for members."""
    service = FakeBusinessService()
    client, user = build_client(service)

    with client:
        response = client.get("/api/v1/businesses/BUS-001")

    assert response.status_code == HTTP_OK
    assert response.json()["data"]["legal_name"] == "TaxPilot Labs Private Limited"
    assert service.business_code == "BUS-001"
    assert service.user_id == user.id


def test_update_business() -> None:
    """Patch endpoint delegates updates to service."""
    service = FakeBusinessService()
    client, user = build_client(service)

    with client:
        response = client.patch(
            "/api/v1/businesses/BUS-001",
            json={"trade_name": "TaxPilot"},
        )

    assert response.status_code == HTTP_OK
    assert response.json()["data"]["trade_name"] == "TaxPilot"
    assert service.business_code == "BUS-001"
    assert service.user_id == user.id
    assert service.updated_request is not None


def test_archive_business() -> None:
    """Delete endpoint archives a business and returns no content."""
    service = FakeBusinessService()
    client, user = build_client(service)

    with client:
        response = client.delete("/api/v1/businesses/BUS-001")

    assert response.status_code == HTTP_NO_CONTENT
    assert response.content == b""
    assert service.archived is True
    assert service.user_id == user.id


def test_unauthorized_request() -> None:
    """Business endpoints require authentication."""
    service = FakeBusinessService()
    client, _user = build_client(service, authenticated=False)

    with client:
        response = client.get("/api/v1/businesses/")

    assert response.status_code == HTTP_UNAUTHORIZED
    assert response.json()["data"]["code"] == "authentication.required"


def test_non_member_request() -> None:
    """Non-member business access is returned as 403."""
    service = FakeBusinessService(
        error=BusinessNotMemberException("User is not a member of the business")
    )
    client, _user = build_client(service)

    with client:
        response = client.get("/api/v1/businesses/BUS-001")

    assert response.status_code == HTTP_FORBIDDEN
    assert response.json()["data"]["code"] == "business.not_member"


def test_openapi_documents_business_routes() -> None:
    """OpenAPI includes business route documentation."""
    service = FakeBusinessService()
    client, _user = build_client(service)

    with client:
        schema = client.get("/openapi.json").json()

    assert "/api/v1/businesses/" in schema["paths"]
    assert "/api/v1/businesses/{business_code}" in schema["paths"]
    assert schema["paths"]["/api/v1/businesses/"]["post"]["summary"] == (
        "Create business"
    )
    assert schema["paths"]["/api/v1/businesses/"]["get"]["summary"] == (
        "List businesses"
    )
    assert schema["paths"]["/api/v1/businesses/{business_code}"]["get"][
        "summary"
    ] == "Get business"
