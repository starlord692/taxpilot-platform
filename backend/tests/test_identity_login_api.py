"""Tests for identity login API."""

import uuid

from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.identity.api.dependencies import get_authentication_service
from app.modules.identity.exceptions import (
    AuthenticationAccountDisabledException,
    AuthenticationAccountLockedException,
    AuthenticationEmailNotVerifiedException,
    AuthenticationInvalidCredentialsException,
)
from app.modules.identity.schemas import LoginRequest
from app.modules.identity.services import AuthenticationResult

HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_LOCKED = 423
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401


class FakeAuthenticationService:
    """Fake authentication service for API tests."""

    def __init__(self, *, error: Exception | None = None) -> None:
        """Initialize fake behavior."""
        self.error = error
        self.received_request: LoginRequest | None = None

    async def authenticate(self, request: LoginRequest) -> AuthenticationResult:
        """Return an authentication result or raise configured error."""
        self.received_request = request
        if self.error is not None:
            raise self.error
        return AuthenticationResult(
            user_id=uuid.uuid4(),
            email=request.email,
            roles=["member"],
            permissions=["identity.users.read"],
        )


def build_payload() -> dict[str, str]:
    """Build a valid login payload."""
    return {
        "email": "OWNER@EXAMPLE.COM",
        "password": "StrongPassword123!",
    }


def build_client(service: FakeAuthenticationService) -> TestClient:
    """Build a test client with authentication service override."""
    app = create_app(initialize_resources=False)
    app.dependency_overrides[get_authentication_service] = lambda: service
    return TestClient(app)


def test_successful_login() -> None:
    """Login API returns authentication context without tokens."""
    service = FakeAuthenticationService()

    with build_client(service) as client:
        response = client.post("/api/v1/identity/login", json=build_payload())

    assert response.status_code == HTTP_OK
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "User authenticated successfully"
    assert payload["data"]["email"] == "owner@example.com"
    assert payload["data"]["roles"] == ["member"]
    assert payload["data"]["permissions"] == ["identity.users.read"]
    assert "access_token" not in payload["data"]
    assert "refresh_token" not in payload["data"]
    assert service.received_request is not None
    assert service.received_request.email == "owner@example.com"


def test_invalid_email_returns_bad_request() -> None:
    """Login API validates email input."""
    payload = build_payload()
    payload["email"] = "not-an-email"

    with build_client(FakeAuthenticationService()) as client:
        response = client.post("/api/v1/identity/login", json=payload)

    assert response.status_code == HTTP_BAD_REQUEST
    assert response.json()["success"] is False


def test_wrong_password_returns_unauthorized() -> None:
    """Login API maps invalid credentials to 401."""
    service = FakeAuthenticationService(
        error=AuthenticationInvalidCredentialsException("Invalid credentials")
    )

    with build_client(service) as client:
        response = client.post("/api/v1/identity/login", json=build_payload())

    assert response.status_code == HTTP_UNAUTHORIZED
    assert response.json()["data"]["code"] == "authentication.invalid_credentials"


def test_pending_account_returns_forbidden() -> None:
    """Login API maps pending accounts to email-not-verified errors."""
    service = FakeAuthenticationService(
        error=AuthenticationEmailNotVerifiedException("Email is not verified")
    )

    with build_client(service) as client:
        response = client.post("/api/v1/identity/login", json=build_payload())

    assert response.status_code == HTTP_FORBIDDEN
    assert response.json()["data"]["code"] == "authentication.email_not_verified"


def test_locked_account_returns_locked() -> None:
    """Login API maps locked accounts to 423."""
    service = FakeAuthenticationService(
        error=AuthenticationAccountLockedException("Account is locked")
    )

    with build_client(service) as client:
        response = client.post("/api/v1/identity/login", json=build_payload())

    assert response.status_code == HTTP_LOCKED
    assert response.json()["data"]["code"] == "authentication.account_locked"


def test_disabled_account_returns_forbidden() -> None:
    """Login API maps disabled accounts to 403."""
    service = FakeAuthenticationService(
        error=AuthenticationAccountDisabledException("Account is disabled")
    )

    with build_client(service) as client:
        response = client.post("/api/v1/identity/login", json=build_payload())

    assert response.status_code == HTTP_FORBIDDEN
    assert response.json()["data"]["code"] == "authentication.account_disabled"


def test_openapi_documents_login_route() -> None:
    """OpenAPI includes login documentation."""
    with build_client(FakeAuthenticationService()) as client:
        schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/api/v1/identity/login"]["post"]
    assert operation["summary"] == "Authenticate identity user"
    assert "200" in operation["responses"]
    assert "400" in operation["responses"]
    assert "401" in operation["responses"]
    assert "403" in operation["responses"]
    assert "423" in operation["responses"]
    assert "500" in operation["responses"]
