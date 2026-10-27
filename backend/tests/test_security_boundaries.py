"""Focused security boundary, tenant isolation, and CORS regression tests."""

import uuid
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, Mock

from fastapi import Request
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.modules.accounting.financial_performance_evidence.models import (
    FinancialPerformanceEvidenceError,
)
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.business_understanding.api.dependencies import (
    get_business_understanding_service,
)
from app.modules.documents.api.dependencies import (
    get_document_service,
    get_document_unit_of_work,
)
from app.modules.documents.schemas import DocumentResponse
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus
from app.modules.identity.services import TokenService
from app.modules.momentum.api.dependencies import get_momentum_service
from app.modules.momentum.service import FinancialPerformanceMomentumService

AUTH_USER_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
AUTH_BUSINESS_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
OTHER_BUSINESS_ID = uuid.UUID("90000000-0000-0000-0000-000000000099")


def build_test_user(*, status: UserStatus = UserStatus.ACTIVE) -> IdentityUser:
    """Build an in-memory identity user."""
    return IdentityUser(
        id=AUTH_USER_ID,
        email="testuser@example.com",
        first_name="Test",
        last_name="User",
        status=status,
    )


def test_unauthenticated_protected_endpoint_rejected() -> None:
    """Unauthenticated requests to protected endpoints return 401."""
    app = create_app(initialize_resources=False)
    client = TestClient(app)

    response = client.post(
        "/api/v1/momentum/financial-performance/evaluate",
        json={"business_id": str(AUTH_BUSINESS_ID)},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    json_body = response.json()
    assert json_body["success"] is False
    assert "Authentication required" in json_body["message"]


def test_malformed_authorization_header_rejected() -> None:
    """Malformed Authorization headers return 401."""
    app = create_app(initialize_resources=False)
    client = TestClient(app)

    headers = {"Authorization": "Basic not-a-bearer-token"}
    response = client.post(
        "/api/v1/momentum/financial-performance/evaluate",
        json={"business_id": str(AUTH_BUSINESS_ID)},
        headers=headers,
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert "malformed" in response.json()["message"].lower()


def test_invalid_jwt_token_rejected() -> None:
    """Forged or invalid JWT token returns 401."""
    app = create_app(initialize_resources=False)
    test_settings = Settings(
        identity_token_secret_key="test-secret-key-that-is-at-least-32-chars-long!",
    )
    token_service = TokenService(settings=test_settings, unit_of_work_factory=Mock())
    app.state.identity_token_service_factory = lambda: token_service

    client = TestClient(app)

    headers = {"Authorization": "Bearer forged.invalid.token"}
    response = client.post(
        "/api/v1/momentum/financial-performance/evaluate",
        json={"business_id": str(AUTH_BUSINESS_ID)},
        headers=headers,
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    json_body = response.json()
    assert json_body["success"] is False
    assert json_body["data"]["code"] == "token.invalid"


def test_disabled_user_account_rejected() -> None:
    """Disabled user account returns 403 Forbidden."""
    app = create_app(initialize_resources=False)

    async def fake_loader(_request: Request, _user_id: uuid.UUID) -> IdentityUser:
        return build_test_user(status=UserStatus.DISABLED)

    app.state.identity_user_loader = fake_loader

    token_service_mock = Mock()
    claims_mock = Mock()
    claims_mock.user_id = AUTH_USER_ID
    token_service_mock.validate_access_token.return_value = claims_mock
    app.state.identity_token_service_factory = lambda: token_service_mock

    client = TestClient(app)
    headers = {"Authorization": "Bearer valid-token-for-disabled-user"}
    response = client.post(
        "/api/v1/momentum/financial-performance/evaluate",
        json={"business_id": str(AUTH_BUSINESS_ID)},
        headers=headers,
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "Account is disabled" in response.json()["message"]


def test_cross_business_scope_violation_returns_403() -> None:
    """Unauthorized cross-business evaluation request returns 403 Forbidden."""
    app = create_app(initialize_resources=False)
    app.dependency_overrides[get_current_user] = build_test_user

    mock_provider = Mock()
    mock_provider.resolve_financial_performance_observation_contexts = AsyncMock(
        return_value=FinancialPerformanceEvidenceError(
            code="UNAUTHORIZED_BUSINESS_SCOPE",
            detail="Authorization does not permit the requested business scope.",
        )
    )

    service = FinancialPerformanceMomentumService(afpe_provider=mock_provider)
    app.dependency_overrides[get_momentum_service] = lambda: service

    client = TestClient(app)
    response = client.post(
        "/api/v1/momentum/financial-performance/evaluate",
        json={
            "business_id": str(OTHER_BUSINESS_ID),
            "current_observation_context": {
                "granularity": "MONTHLY",
                "period_type": "CALENDAR",
                "observation_period_id": "period-1",
            },
            "evidence_perspective": "HISTORICAL_REPORTED",
            "requested_comparison_kind": "PREVIOUS_COMPARABLE_PERIOD",
        },
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert (
        "Authorization does not permit the requested business scope"
        in response.json()["message"]
    )


def test_cross_business_understanding_access_rejected() -> None:
    """Non-member access to business understanding returns 403 Forbidden."""
    app = create_app(initialize_resources=False)
    app.dependency_overrides[get_current_user] = build_test_user

    mock_service = Mock()
    mock_service.get_snapshot = AsyncMock(
        side_effect=BusinessNotMemberException(
            "User is not a member of this business",
            details={"business_id": str(OTHER_BUSINESS_ID)},
        )
    )
    app.dependency_overrides[get_business_understanding_service] = lambda: mock_service

    client = TestClient(app)
    response = client.get(
        "/api/v1/business-understanding",
        params={"business_id": str(OTHER_BUSINESS_ID)},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    json_body = response.json()
    assert json_body["success"] is False
    assert json_body["data"]["code"] == "business.not_member"


def test_cross_business_document_access_rejected() -> None:
    """Accessing documents across different business scopes returns 403 Forbidden."""
    app = create_app(initialize_resources=False)
    app.dependency_overrides[get_current_user] = build_test_user

    doc_id = uuid.uuid4()
    mock_uow = Mock()
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    mock_uow.business_memberships.is_member = AsyncMock(return_value=True)

    # Return doc for OTHER_BUSINESS_ID while caller asked under AUTH_BUSINESS_ID
    mock_doc = Mock(spec=DocumentResponse)
    mock_doc.business_id = OTHER_BUSINESS_ID

    mock_service = Mock()
    mock_service.process_ocr = AsyncMock(return_value=mock_doc)

    app.dependency_overrides[get_document_unit_of_work] = lambda: mock_uow
    app.dependency_overrides[get_document_service] = lambda: mock_service

    client = TestClient(app)
    response = client.post(
        f"/api/v1/documents/{doc_id}/ocr",
        params={"business_id": str(AUTH_BUSINESS_ID)},
        json={"provider": "tesseract", "language": "eng"},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    json_body = response.json()
    assert json_body["success"] is False
    assert json_body["data"]["code"] == "business.not_member"
    assert "Document does not belong to the requested business" in json_body["message"]


def test_missing_business_scope_fails_closed() -> None:
    """Missing required business scope parameters fail closed with 400 Bad Request."""
    app = create_app(initialize_resources=False)
    app.dependency_overrides[get_current_user] = build_test_user
    client = TestClient(app)

    # Missing business_id in request body
    post_res = client.post(
        "/api/v1/momentum/financial-performance/evaluate",
        json={},
    )
    assert post_res.status_code == HTTPStatus.BAD_REQUEST

    # Missing business_id query parameter
    get_res = client.get("/api/v1/business-understanding")
    assert get_res.status_code == HTTPStatus.BAD_REQUEST


def test_unhandled_exception_does_not_leak_details() -> None:
    """Unhandled internal exceptions return clean 500 without stack trace leaks."""
    app = create_app(initialize_resources=False)

    @app.get("/test-internal-error")
    def trigger_error() -> Any:
        raise RuntimeError(
            "Internal DB connection failed: postgresql://admin:secret@host/db"
        )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/test-internal-error")

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    json_body = response.json()
    assert json_body["success"] is False
    assert json_body["message"] == "Internal server error"
    assert "secret" not in response.text
    assert "Traceback" not in response.text


def test_cors_headers_on_preflight() -> None:
    """Approved origin preflight returns 200 with credentials and origin."""
    app = create_app(initialize_resources=False)
    client = TestClient(app)

    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert (
        response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    )
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_unapproved_origin_preflight_rejected() -> None:
    """Unapproved origin preflight is rejected with 400 and no origin header."""
    app = create_app(initialize_resources=False)
    client = TestClient(app)

    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://unapproved-origin.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.headers.get("access-control-allow-origin") is None


def test_cors_unapproved_origin_request_has_no_allow_headers() -> None:
    """Direct request from unapproved origin receives no CORS allow header."""
    app = create_app(initialize_resources=False)
    client = TestClient(app)

    response = client.get(
        "/api/v1/health",
        headers={"Origin": "http://unapproved-origin.com"},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.headers.get("access-control-allow-origin") is None


def test_cors_approved_origin_credentials_and_methods() -> None:
    """Approved origin preflight returns explicit methods, headers, and credentials."""
    app = create_app(initialize_resources=False)
    client = TestClient(app)

    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert (
        response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    )
    assert response.headers.get("access-control-allow-credentials") == "true"
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "POST" in allow_methods
    assert "GET" in allow_methods
    allow_headers = response.headers.get("access-control-allow-headers", "")
    assert "authorization" in allow_headers.lower()
