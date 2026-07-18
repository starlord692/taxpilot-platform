"""Tests for identity authentication middleware and current user dependency."""

import uuid
from datetime import timedelta

from fastapi import Request
from fastapi.testclient import TestClient

from app.common.models.abstract.timestamp import utc_now
from app.main import create_app
from app.modules.identity.exceptions import TokenExpiredException, TokenInvalidException
from app.modules.identity.models import IdentityUser, UserStatus
from app.modules.identity.services import AccessTokenClaims

HTTP_FORBIDDEN = 403
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401


class FakeTokenService:
    """Fake token service for middleware tests."""

    def __init__(
        self,
        *,
        user_id: uuid.UUID,
        error: Exception | None = None,
    ) -> None:
        """Initialize fake validation behavior."""
        self.user_id = user_id
        self.error = error
        self.received_token: str | None = None

    def validate_access_token(self, token: str) -> AccessTokenClaims:
        """Return access claims or raise configured validation error."""
        self.received_token = token
        if self.error is not None:
            raise self.error
        issued_at = utc_now()
        return AccessTokenClaims(
            user_id=self.user_id,
            email="owner@example.com",
            roles=["member"],
            permissions=["identity.users.read"],
            issued_at=issued_at,
            expires_at=issued_at + timedelta(minutes=15),
            token_type="access",
        )


def build_user(
    *,
    user_id: uuid.UUID,
    status: UserStatus = UserStatus.ACTIVE,
    is_deleted: bool = False,
) -> IdentityUser:
    """Build an identity user model for request-state tests."""
    return IdentityUser(
        id=user_id,
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=status,
        failed_login_attempts=0,
        is_deleted=is_deleted,
    )


def build_client(
    *,
    token_service: FakeTokenService,
    user: IdentityUser | None,
) -> TestClient:
    """Build a test client with middleware dependencies overridden."""
    app = create_app(initialize_resources=False)

    async def load_user(_request: Request, _user_id: uuid.UUID) -> IdentityUser | None:
        return user

    app.state.identity_token_service_factory = lambda: token_service
    app.state.identity_user_loader = load_user
    return TestClient(app)


def test_valid_token_returns_me() -> None:
    """Valid bearer token attaches the user and /me returns the profile."""
    user_id = uuid.uuid4()
    token_service = FakeTokenService(user_id=user_id)
    user = build_user(user_id=user_id)

    with build_client(token_service=token_service, user=user) as client:
        response = client.get(
            "/api/v1/identity/me",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == HTTP_OK
    payload = response.json()
    assert payload["id"] == str(user_id)
    assert payload["email"] == "owner@example.com"
    assert token_service.received_token == "valid-token"


def test_invalid_token_returns_unauthorized() -> None:
    """Invalid bearer tokens are rejected by middleware."""
    user_id = uuid.uuid4()
    token_service = FakeTokenService(
        user_id=user_id,
        error=TokenInvalidException("Invalid access token"),
    )

    with build_client(
        token_service=token_service,
        user=build_user(user_id=user_id),
    ) as client:
        response = client.get(
            "/api/v1/identity/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == HTTP_UNAUTHORIZED
    assert response.json()["data"]["code"] == "token.invalid"


def test_expired_token_returns_unauthorized() -> None:
    """Expired bearer tokens are rejected by middleware."""
    user_id = uuid.uuid4()
    token_service = FakeTokenService(
        user_id=user_id,
        error=TokenExpiredException("Access token has expired"),
    )

    with build_client(
        token_service=token_service,
        user=build_user(user_id=user_id),
    ) as client:
        response = client.get(
            "/api/v1/identity/me",
            headers={"Authorization": "Bearer expired-token"},
        )

    assert response.status_code == HTTP_UNAUTHORIZED
    assert response.json()["data"]["code"] == "token.expired"


def test_missing_authorization_header_returns_unauthorized() -> None:
    """Protected endpoints require an authenticated user."""
    user_id = uuid.uuid4()

    with build_client(
        token_service=FakeTokenService(user_id=user_id),
        user=build_user(user_id=user_id),
    ) as client:
        response = client.get("/api/v1/identity/me")

    assert response.status_code == HTTP_UNAUTHORIZED
    assert response.json()["data"]["code"] == "authentication.required"


def test_malformed_authorization_header_returns_unauthorized() -> None:
    """Malformed Authorization headers are rejected."""
    user_id = uuid.uuid4()

    with build_client(
        token_service=FakeTokenService(user_id=user_id),
        user=build_user(user_id=user_id),
    ) as client:
        response = client.get(
            "/api/v1/identity/me",
            headers={"Authorization": "Basic invalid"},
        )

    assert response.status_code == HTTP_UNAUTHORIZED
    assert response.json()["data"]["code"] == "authentication.required"


def test_disabled_user_returns_forbidden() -> None:
    """Disabled users are rejected after token validation."""
    user_id = uuid.uuid4()

    with build_client(
        token_service=FakeTokenService(user_id=user_id),
        user=build_user(user_id=user_id, status=UserStatus.DISABLED),
    ) as client:
        response = client.get(
            "/api/v1/identity/me",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == HTTP_FORBIDDEN
    assert response.json()["data"]["code"] == "authentication.account_disabled"


def test_deleted_user_returns_unauthorized() -> None:
    """Deleted users are rejected after token validation."""
    user_id = uuid.uuid4()

    with build_client(
        token_service=FakeTokenService(user_id=user_id),
        user=build_user(user_id=user_id, is_deleted=True),
    ) as client:
        response = client.get(
            "/api/v1/identity/me",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == HTTP_UNAUTHORIZED
    assert response.json()["data"]["code"] == "authentication.user_unavailable"


def test_missing_user_returns_unauthorized() -> None:
    """Tokens whose subject no longer resolves to a user are rejected."""
    user_id = uuid.uuid4()

    with build_client(
        token_service=FakeTokenService(user_id=user_id),
        user=None,
    ) as client:
        response = client.get(
            "/api/v1/identity/me",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == HTTP_UNAUTHORIZED
    assert response.json()["data"]["code"] == "authentication.user_unavailable"


def test_openapi_documents_bearer_auth_for_me() -> None:
    """OpenAPI documents bearer authentication for /me."""
    user_id = uuid.uuid4()

    with build_client(
        token_service=FakeTokenService(user_id=user_id),
        user=build_user(user_id=user_id),
    ) as client:
        schema = client.get("/openapi.json").json()

    assert "Bearer Authentication" in schema["components"]["securitySchemes"]
    operation = schema["paths"]["/api/v1/identity/me"]["get"]
    assert operation["summary"] == "Get current identity user"
    assert operation["security"] == [{"Bearer Authentication": []}]
