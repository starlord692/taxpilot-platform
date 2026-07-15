"""Tests for identity registration API."""

import uuid

from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.identity.api.dependencies import get_registration_service
from app.modules.identity.exceptions import IdentityEmailAlreadyExistsException
from app.modules.identity.models import UserStatus
from app.modules.identity.schemas import CreateUserRequest, UserResponse

HTTP_BAD_REQUEST = 400
HTTP_CONFLICT = 409
HTTP_CREATED = 201


class FakeRegistrationService:
    """Fake registration service for API tests."""

    def __init__(self, *, duplicate_email: bool = False) -> None:
        """Initialize fake behavior flags."""
        self.duplicate_email = duplicate_email
        self.received_request: CreateUserRequest | None = None

    async def register_user(self, request: CreateUserRequest) -> UserResponse:
        """Return a user response or raise a duplicate email error."""
        self.received_request = request
        if self.duplicate_email:
            raise IdentityEmailAlreadyExistsException(
                "Email already exists",
                details={"email": request.email},
            )
        return UserResponse(
            id=uuid.uuid4(),
            email=request.email,
            first_name=request.first_name,
            last_name=request.last_name,
            display_name=request.display_name or "Jane Doe",
            status=UserStatus.PENDING,
            last_login_at=None,
            failed_login_attempts=0,
            locked_until=None,
        )


def build_payload() -> dict[str, str]:
    """Build a valid registration payload."""
    return {
        "email": "OWNER@EXAMPLE.COM",
        "first_name": "Jane",
        "last_name": "Doe",
        "display_name": "Jane Doe",
        "password": "StrongPassword123!",
    }


def build_client(service: FakeRegistrationService) -> TestClient:
    """Build a test client with registration service override."""
    app = create_app(initialize_resources=False)
    app.dependency_overrides[get_registration_service] = lambda: service
    return TestClient(app)


def test_successful_registration() -> None:
    """Registration API returns a standardized success response."""
    service = FakeRegistrationService()

    with build_client(service) as client:
        response = client.post("/api/v1/identity/register", json=build_payload())

    assert response.status_code == HTTP_CREATED
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "User registered successfully"
    assert payload["data"]["email"] == "owner@example.com"
    assert payload["data"]["status"] == UserStatus.PENDING
    assert "password_hash" not in payload["data"]
    assert service.received_request is not None
    assert service.received_request.email == "owner@example.com"


def test_duplicate_email_returns_conflict() -> None:
    """Registration API returns 409 for duplicate emails."""
    service = FakeRegistrationService(duplicate_email=True)

    with build_client(service) as client:
        response = client.post("/api/v1/identity/register", json=build_payload())

    assert response.status_code == HTTP_CONFLICT
    assert response.json() == {
        "success": False,
        "message": "Email already exists",
        "data": {
            "code": "identity.email_already_exists",
            "details": {"email": "owner@example.com"},
        },
    }


def test_weak_password_returns_bad_request() -> None:
    """Registration API validates weak passwords."""
    payload = build_payload()
    payload["password"] = "weak"

    with build_client(FakeRegistrationService()) as client:
        response = client.post("/api/v1/identity/register", json=payload)

    assert response.status_code == HTTP_BAD_REQUEST
    assert response.json()["success"] is False


def test_invalid_email_returns_bad_request() -> None:
    """Registration API validates email format."""
    payload = build_payload()
    payload["email"] = "not-an-email"

    with build_client(FakeRegistrationService()) as client:
        response = client.post("/api/v1/identity/register", json=payload)

    assert response.status_code == HTTP_BAD_REQUEST
    assert response.json()["success"] is False


def test_missing_fields_return_bad_request() -> None:
    """Registration API validates required fields."""
    payload = build_payload()
    del payload["email"]

    with build_client(FakeRegistrationService()) as client:
        response = client.post("/api/v1/identity/register", json=payload)

    assert response.status_code == HTTP_BAD_REQUEST
    assert response.json()["success"] is False


def test_openapi_documents_registration_route() -> None:
    """OpenAPI includes registration documentation."""
    with build_client(FakeRegistrationService()) as client:
        schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/api/v1/identity/register"]["post"]
    assert operation["summary"] == "Register identity user"
    assert "201" in operation["responses"]
    assert "400" in operation["responses"]
    assert "409" in operation["responses"]
    assert "500" in operation["responses"]
