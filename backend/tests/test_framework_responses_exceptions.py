"""Tests for framework responses and exceptions."""

from fastapi.testclient import TestClient

from app.common.exceptions import ValidationException
from app.core.exceptions import HTTP_ERROR_CODES
from app.core.responses import ErrorDetail, ErrorResponse, PaginatedApiResponse
from app.main import create_app

HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
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


def test_request_validation_handler_returns_error_response() -> None:
    """Request validation errors use the standard error envelope."""
    app = create_app(initialize_resources=False)

    @app.get("/needs-int")
    async def needs_int(value: int) -> dict[str, int]:
        return {"value": value}

    with TestClient(app) as client:
        response = client.get("/needs-int", params={"value": "not-an-int"})

    payload = response.json()
    assert response.status_code == HTTP_BAD_REQUEST
    assert payload["success"] is False
    assert payload["data"]["code"] == "validation.request_invalid"
    assert payload["data"]["details"]["errors"][0]["loc"] == ["query", "value"]


def test_http_exception_handler_returns_error_response() -> None:
    """Framework HTTP errors use the standard error envelope."""
    app = create_app(initialize_resources=False)

    with TestClient(app) as client:
        response = client.get("/missing-route")

    assert response.status_code == HTTP_NOT_FOUND
    assert response.json() == {
        "success": False,
        "message": "Not Found",
        "data": {
            "code": "http.not_found",
            "details": {"status_code": HTTP_NOT_FOUND},
        },
    }


def test_openapi_documents_runtime_validation_as_bad_request() -> None:
    """Generated OpenAPI docs match the runtime validation status code."""
    schema = create_app(initialize_resources=False).openapi()
    responses = schema["paths"]["/api/v1/identity/register"]["post"]["responses"]

    assert "400" in responses
    assert "422" not in responses
    assert responses["400"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ErrorResponse"
    )
    assert responses["500"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ErrorResponse"
    )


def test_http_error_code_map_documents_common_statuses() -> None:
    """Common framework HTTP statuses map to stable public error codes."""
    assert HTTP_ERROR_CODES[HTTP_BAD_REQUEST] == "http.bad_request"
    assert HTTP_ERROR_CODES[HTTP_NOT_FOUND] == "http.not_found"