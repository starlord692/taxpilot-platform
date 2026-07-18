"""Tests for framework responses and exceptions."""

from fastapi.testclient import TestClient

from app.common.exceptions import ValidationException
from app.core.responses import ErrorDetail, ErrorResponse, PaginatedApiResponse
from app.main import create_app

HTTP_BAD_REQUEST = 400
EXPECTED_RESPONSE_PAGES = 3


def test_error_response_uses_structured_detail() -> None:
    """Error responses contain stable error details."""
    response = ErrorResponse(
        success=False,
        message="Invalid input",
        data=ErrorDetail(code="validation_error"),
    )

    assert response.data is not None
    assert response.data.code == "validation_error"
    assert response.data.details == {}


def test_paginated_api_response_includes_meta() -> None:
    """Paginated API responses include pagination metadata."""
    response = PaginatedApiResponse[int](
        success=True,
        message="OK",
        data=[1, 2],
        meta={"page": 1, "size": 2, "total": 5},
    )

    assert response.meta.pages == EXPECTED_RESPONSE_PAGES


def test_taxpilot_exception_handler_returns_error_response() -> None:
    """Application exception handler returns the standard error envelope."""
    app = create_app(initialize_resources=False)

    @app.get("/raise-validation")
    async def raise_validation() -> None:
        raise ValidationException("Invalid request", details={"field": "name"})

    with TestClient(app) as client:
        response = client.get("/raise-validation")

    assert response.status_code == HTTP_BAD_REQUEST
    assert response.json() == {
        "success": False,
        "message": "Invalid request",
        "data": {
            "code": "validation_error",
            "details": {"field": "name"},
        },
    }
