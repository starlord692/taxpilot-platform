"""Tests for identity session API."""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from app.common.models.abstract.timestamp import utc_now
from app.main import create_app
from app.modules.identity.api.dependencies import (
    get_authentication_service,
    get_token_service,
)
from app.modules.identity.exceptions import (
    AuthenticationAccountDisabledException,
    AuthenticationAccountLockedException,
    AuthenticationEmailNotVerifiedException,
    AuthenticationInvalidCredentialsException,
)
from app.modules.identity.schemas import LoginRequest
from app.modules.identity.services import AuthenticationResult, RefreshTokenResult

HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_LOCKED = 423
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
ACCESS_TOKEN_EXPIRES_IN = 900


class FakeAuthenticationService:
    """Fake authentication service for session API tests."""

    def __init__(self, *, error: Exception | None = None) -> None:
        """Initialize fake behavior."""
        self.error = error
        self.received_request: LoginRequest | None = None
        self.result = AuthenticationResult(
            user_id=uuid.uuid4(),
            email="owner@example.com",
            roles=["member"],
            permissions=["identity.users.read"],
        )

    async def authenticate(self, request: LoginRequest) -> AuthenticationResult:
        """Return an authentication result or raise configured error."""
        self.received_request = request
        if self.error is not None:
            raise self.error
        return self.result


class FakeTokenService:
    """Fake token service for session API tests."""

    access_token_expires_in = ACCESS_TOKEN_EXPIRES_IN

    def __init__(self) -> None:
        """Initialize token service fake state."""
        self.access_input: AuthenticationResult | None = None
        self.refresh_input: AuthenticationResult | None = None

    def generate_access_token(
        self,
        authentication_result: AuthenticationResult,
    ) -> str:
        """Return a deterministic access token."""
        self.access_input = authentication_result
        return "access-token"

    async def generate_refresh_token(
        self,
        authentication_result: AuthenticationResult,
    ) -> RefreshTokenResult:
        """Return a deterministic refresh token."""
        self.refresh_input = authentication_result
        return RefreshTokenResult(
            token="refresh-token",
            user_id=authentication_result.user_id,
            expires_at=utc_now() + timedelta(days=30),
        )


def build_payload() -> dict[str, str]:
    """Build a valid session payload."""
    return {
        "email": "OWNER@EXAMPLE.COM",
        "password": "StrongPassword123!",
    }


def build_client(
    authentication_service: FakeAuthenticationService,
    token_service: FakeTokenService | None = None,
) -> TestClient:
    """Build a test client with service overrides."""
    app = create_app(initialize_resources=False)
    app.dependency_overrides[get_authentication_service] = (
        lambda: authentication_service
    )
    app.dependency_overrides[get_token_service] = (
        lambda: token_service or FakeTokenService()
    )
    return TestClient(app)


def test_successful_session_login() -> None:
    """Session API authenticates and returns tokens with user context."""
    authentication_service = FakeAuthenticationService()
    token_service = FakeTokenService()

    with build_client(authentication_service, token_service) as client:
        response = client.post("/api/v1/identity/session", json=build_payload())

    assert response.status_code == HTTP_OK
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "Login session created successfully"
    assert payload["data"]["access_token"] == "access-token"
    assert payload["data"]["refresh_token"] == "refresh-token"
    assert payload["data"]["token_type"] == "Bearer"
    assert payload["data"]["expires_in"] == ACCESS_TOKEN_EXPIRES_IN
    assert payload["data"]["user"] == {
        "id": str(authentication_service.result.user_id),
        "email": "owner@example.com",
        "roles": ["member"],
        "permissions": ["identity.users.read"],
    }
    assert authentication_service.received_request is not None
    assert authentication_service.received_request.email == "owner@example.com"
    assert token_service.access_input == authentication_service.result
    assert token_service.refresh_input == authentication_service.result


def test_wrong_password_returns_unauthorized() -> None:
    """Session API maps wrong passwords to 401."""
    service = FakeAuthenticationService(
        error=AuthenticationInvalidCredentialsException("Invalid credentials")
    )

    with build_client(service) as client:
        response = client.post("/api/v1/identity/session", json=build_payload())

    assert response.status_code == HTTP_UNAUTHORIZED
    assert response.json()["data"]["code"] == "authentication.invalid_credentials"


def test_unknown_email_returns_unauthorized() -> None:
    """Session API maps unknown email to 401."""
    service = FakeAuthenticationService(
        error=AuthenticationInvalidCredentialsException("Invalid credentials")
    )

    with build_client(service) as client:
        response = client.post("/api/v1/identity/session", json=build_payload())

    assert response.status_code == HTTP_UNAUTHORIZED
    assert response.json()["data"]["code"] == "authentication.invalid_credentials"


def test_pending_account_returns_forbidden() -> None:
    """Session API maps pending accounts to email-not-verified errors."""
    service = FakeAuthenticationService(
        error=AuthenticationEmailNotVerifiedException("Email is not verified")
    )

    with build_client(service) as client:
        response = client.post("/api/v1/identity/session", json=build_payload())

    assert response.status_code == HTTP_FORBIDDEN
    assert response.json()["data"]["code"] == "authentication.email_not_verified"


def test_locked_account_returns_locked() -> None:
    """Session API maps locked accounts to 423."""
    service = FakeAuthenticationService(
        error=AuthenticationAccountLockedException("Account is locked")
    )

    with build_client(service) as client:
        response = client.post("/api/v1/identity/session", json=build_payload())

    assert response.status_code == HTTP_LOCKED
    assert response.json()["data"]["code"] == "authentication.account_locked"


def test_disabled_account_returns_forbidden() -> None:
    """Session API maps disabled accounts to 403."""
    service = FakeAuthenticationService(
        error=AuthenticationAccountDisabledException("Account is disabled")
    )

    with build_client(service) as client:
        response = client.post("/api/v1/identity/session", json=build_payload())

    assert response.status_code == HTTP_FORBIDDEN
    assert response.json()["data"]["code"] == "authentication.account_disabled"


def test_invalid_email_returns_bad_request() -> None:
    """Session API validates email input."""
    payload = build_payload()
    payload["email"] = "not-an-email"

    with build_client(FakeAuthenticationService()) as client:
        response = client.post("/api/v1/identity/session", json=payload)

    assert response.status_code == HTTP_BAD_REQUEST
    assert response.json()["success"] is False


def test_openapi_documents_session_route() -> None:
    """OpenAPI includes session documentation."""
    with build_client(FakeAuthenticationService()) as client:
        schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/api/v1/identity/session"]["post"]
    assert operation["summary"] == "Create identity login session"
    assert "200" in operation["responses"]
    assert "400" in operation["responses"]
    assert "401" in operation["responses"]
    assert "403" in operation["responses"]
    assert "423" in operation["responses"]
    assert "500" in operation["responses"]
