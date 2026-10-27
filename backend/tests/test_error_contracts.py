"""Comprehensive tests for API and error contract consistency (EP-RC1.6).

Verifies that:
1. Domain exceptions return canonical ErrorResponse with HTTP 4xx.
2. Starlette HTTP exceptions return canonical ErrorResponse.
3. Request validation failures return HTTP 400 with ValidationErrorResponse.
4. Unhandled server errors return HTTP 500 without leaking sensitive data.
5. All error envelopes share the canonical ApiResponse schema structure.
6. Real API endpoints across modules maintain consistent error structures.
7. OpenAPI schema contains zero 422 responses and documents 400.
8. Parameterized tests detect any documented vs runtime schema mismatches.
9. Successful response contracts remain untouched and well-typed.
10. Obsolete FastAPI validation schemas are eliminated.
"""

import uuid
from collections.abc import Generator
from http import HTTPStatus
from typing import Any

import pydantic
import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.core.config import Settings, get_settings
from app.core.responses import ErrorResponse, ValidationErrorResponse
from app.main import app as prod_app
from app.main import create_app
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.exceptions import AuthenticationRequiredException
from app.modules.identity.models import IdentityUser, UserStatus

HTTP_OK = HTTPStatus.OK.value
HTTP_BAD_REQUEST = HTTPStatus.BAD_REQUEST.value
HTTP_UNAUTHORIZED = HTTPStatus.UNAUTHORIZED.value
HTTP_FORBIDDEN = HTTPStatus.FORBIDDEN.value
HTTP_NOT_FOUND = HTTPStatus.NOT_FOUND.value
HTTP_METHOD_NOT_ALLOWED = HTTPStatus.METHOD_NOT_ALLOWED.value
HTTP_CONFLICT = HTTPStatus.CONFLICT.value
HTTP_INTERNAL_SERVER_ERROR = HTTPStatus.INTERNAL_SERVER_ERROR.value

VAL_RESP_REF = "#/components/schemas/ValidationErrorResponse"
ERR_RESP_REF = "#/components/schemas/ErrorResponse"
TOTAL_EXPECTED_400_OPERATIONS = 117


class SampleRequestBody(BaseModel):
    """Sample payload for validation testing."""

    name: str = Field(min_length=3)
    quantity: int = Field(gt=0)
    email: str


@pytest.fixture
def test_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """Create a test application instance with synthetic test endpoints."""
    monkeypatch.setenv(
        "IDENTITY_TOKEN_SECRET_KEY",
        "test-secret-key-32-bytes-long!",
    )
    get_settings.cache_clear()

    user = IdentityUser(
        id=uuid.uuid4(),
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=UserStatus.ACTIVE,
        failed_login_attempts=0,
    )

    app = create_app(
        settings=Settings(
            environment="testing",
            secret_key="test-secret-key-32-bytes-long!",
            identity_token_secret_key="test-secret-key-32-bytes-long!",
        ),
        initialize_resources=False,
    )
    app.dependency_overrides[get_current_user] = lambda: user

    @app.get("/test/raise-not-found")
    async def raise_not_found() -> None:
        raise NotFoundException(
            "Customer not found",
            details={"customer_id": "cust-123"},
        )

    @app.get("/test/raise-conflict")
    async def raise_conflict() -> None:
        raise ConflictException(
            "Invoice number already exists",
            details={"invoice_no": "INV-01"},
        )

    @app.get("/test/raise-validation")
    async def raise_domain_validation() -> None:
        raise ValidationException(
            "Discount cannot exceed total",
            details={"max_discount": 100},
        )

    @app.get("/test/raise-unauthorized")
    async def raise_unauthorized() -> None:
        raise AuthenticationRequiredException("Authentication is required")

    @app.get("/test/raise-forbidden")
    async def raise_forbidden() -> None:
        raise BusinessNotMemberException("User is not a business member")

    @app.get("/test/raise-http-404")
    async def raise_http_404() -> None:
        raise StarletteHTTPException(
            status_code=HTTP_NOT_FOUND,
            detail="Page not found",
        )

    @app.get("/test/raise-http-405")
    async def raise_http_405() -> None:
        raise StarletteHTTPException(
            status_code=HTTP_METHOD_NOT_ALLOWED,
            detail="Method not allowed for this route",
        )

    @app.post("/test/validate-payload")
    async def validate_payload(
        payload: SampleRequestBody,  # noqa: ARG001
        filter_type: str = Query(..., min_length=2),  # noqa: ARG001
    ) -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/test/raise-unhandled-error")
    async def raise_unhandled() -> None:
        secret_db = "postgres://admin:SUPER_SECRET_PW@db.internal:5432/taxpilot"
        msg = f"Database crashed with connection: {secret_db}"
        raise RuntimeError(msg)

    return app


@pytest.fixture
def client(test_app: FastAPI) -> Generator[TestClient, None, None]:
    """TestClient fixture for the test application."""
    with TestClient(test_app, raise_server_exceptions=False) as c:
        yield c


def test_domain_not_found_exception_contract(client: TestClient) -> None:
    """NotFoundException produces HTTP 404 with standard ErrorResponse envelope."""
    response = client.get("/test/raise-not-found")
    assert response.status_code == HTTP_NOT_FOUND

    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Customer not found"
    assert isinstance(body["data"], dict)
    assert body["data"]["code"] == "not_found"
    assert body["data"]["details"] == {"customer_id": "cust-123"}


def test_domain_conflict_exception_contract(client: TestClient) -> None:
    """ConflictException produces HTTP 409 with standard ErrorResponse envelope."""
    response = client.get("/test/raise-conflict")
    assert response.status_code == HTTP_CONFLICT

    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Invoice number already exists"
    assert body["data"]["code"] == "conflict"
    assert body["data"]["details"] == {"invoice_no": "INV-01"}


def test_domain_validation_exception_contract(client: TestClient) -> None:
    """ValidationException produces HTTP 400 with standard ErrorResponse envelope."""
    response = client.get("/test/raise-validation")
    assert response.status_code == HTTP_BAD_REQUEST

    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Discount cannot exceed total"
    assert body["data"]["code"] == "validation_error"
    assert body["data"]["details"] == {"max_discount": 100}


def test_domain_auth_exceptions_contract(client: TestClient) -> None:
    """Unauthorized and Forbidden exceptions produce HTTP 401 and 403."""
    unauth_resp = client.get("/test/raise-unauthorized")
    assert unauth_resp.status_code == HTTP_UNAUTHORIZED
    unauth_body = unauth_resp.json()
    assert unauth_body["success"] is False
    assert unauth_body["message"] == "Authentication is required"
    assert unauth_body["data"]["code"] == "authentication.required"

    forbidden_resp = client.get("/test/raise-forbidden")
    assert forbidden_resp.status_code == HTTP_FORBIDDEN
    forbidden_body = forbidden_resp.json()
    assert forbidden_body["success"] is False
    assert forbidden_body["message"] == "User is not a business member"
    assert forbidden_body["data"]["code"] == "business.not_member"


def test_starlette_http_exceptions_contract(client: TestClient) -> None:
    """Starlette HTTP exceptions produce standard ErrorResponse envelopes."""
    res_404 = client.get("/test/raise-http-404")
    assert res_404.status_code == HTTP_NOT_FOUND
    body_404 = res_404.json()
    assert body_404["success"] is False
    assert body_404["message"] == "Page not found"
    assert body_404["data"]["code"] == "not_found"

    res_405 = client.get("/test/raise-http-405")
    assert res_405.status_code == HTTP_METHOD_NOT_ALLOWED
    body_405 = res_405.json()
    assert body_405["success"] is False
    assert body_405["message"] == "Method not allowed for this route"
    assert body_405["data"]["code"] == "method_not_allowed"


def test_request_validation_returns_http_400_not_422(client: TestClient) -> None:
    """FastAPI/Pydantic validation errors return HTTP 400 with envelope."""
    response = client.post(
        "/test/validate-payload",
        json={"name": "a", "quantity": 0, "email": "invalid"},
    )
    assert response.status_code == HTTP_BAD_REQUEST

    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Request validation failed"
    assert isinstance(body["data"], list)
    assert len(body["data"]) > 0

    for item in body["data"]:
        assert "loc" in item
        assert isinstance(item["loc"], list)
        assert "msg" in item
        assert isinstance(item["msg"], str)
        assert "type" in item
        assert isinstance(item["type"], str)

    error_fields = [item["loc"][-1] for item in body["data"]]
    assert "name" in error_fields
    assert "quantity" in error_fields
    assert "filter_type" in error_fields


def test_unhandled_exception_sanitizes_information_leaks(
    client: TestClient,
) -> None:
    """Unhandled internal errors return HTTP 500 without leaking secrets."""
    response = client.get("/test/raise-unhandled-error")
    assert response.status_code == HTTP_INTERNAL_SERVER_ERROR

    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Internal server error"
    assert body["data"]["code"] == "internal_error"
    assert body["data"]["details"] == {}

    raw_body = response.text
    assert "SUPER_SECRET_PW" not in raw_body
    assert "postgres://" not in raw_body
    assert "Traceback" not in raw_body
    assert "RuntimeError" not in raw_body


def test_nonexistent_route_returns_canonical_error_response(
    client: TestClient,
) -> None:
    """Accessing an undefined route returns HTTP 404 with ErrorResponse."""
    response = client.get(f"/api/v1/nonexistent-{uuid.uuid4()}")
    assert response.status_code == HTTP_NOT_FOUND

    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Not Found"
    assert body["data"]["code"] == "not_found"


def test_successful_response_contract_unaffected(client: TestClient) -> None:
    """Successful responses preserve their standard ApiResponse envelopes."""
    response = client.get("/api/v1/health")
    assert response.status_code == HTTP_OK

    body = response.json()
    assert body["success"] is True
    assert body["message"] == "TaxPilot API is healthy"
    assert isinstance(body["data"], dict)
    assert body["data"]["status"] == "UP"


def test_runtime_error_cannot_be_confused_with_validation_error() -> None:
    """Validation and domain error schemas are strictly distinct."""
    # A validation response cannot be parsed as an ErrorResponse
    val_payload: dict[str, Any] = {
        "success": False,
        "message": "Request validation failed",
        "data": [{"loc": ["body", "email"], "msg": "Invalid", "type": "value_error"}],
    }
    val_model = ValidationErrorResponse.model_validate(val_payload)
    assert val_model.success is False
    with pytest.raises(pydantic.ValidationError):
        ErrorResponse.model_validate(val_payload)

    # A domain error response cannot be parsed as a ValidationErrorResponse
    err_payload: dict[str, Any] = {
        "success": False,
        "message": "Not found",
        "data": {"code": "not_found", "details": {}},
    }
    err_model = ErrorResponse.model_validate(err_payload)
    assert err_model.success is False
    with pytest.raises(pydantic.ValidationError):
        ValidationErrorResponse.model_validate(err_payload)


@pytest.mark.parametrize(
    ("method", "request_path", "schema_path", "payload"),
    [
        ("POST", "/api/v1/identity/register", "/api/v1/identity/register", {}),
        (
            "POST",
            "/api/v1/identity/login",
            "/api/v1/identity/login",
            {"email": "invalid"},
        ),
        (
            "POST",
            "/api/v1/identity/session",
            "/api/v1/identity/session",
            {"email": "invalid"},
        ),
        (
            "GET",
            "/api/v1/businesses/?page=not-a-number",
            "/api/v1/businesses/",
            None,
        ),
        (
            "GET",
            "/api/v1/inventory/products?business_id=not-a-uuid",
            "/api/v1/inventory/products",
            None,
        ),
        (
            "GET",
            "/api/v1/inventory/products/not-a-uuid",
            "/api/v1/inventory/products/{product_id}",
            None,
        ),
        (
            "GET",
            "/api/v1/inventory/warehouses/not-a-uuid",
            "/api/v1/inventory/warehouses/{warehouse_id}",
            None,
        ),
        (
            "GET",
            "/api/v1/expenses/not-a-uuid",
            "/api/v1/expenses/{expense_id}",
            None,
        ),
        (
            "GET",
            "/api/v1/sales/invoices/not-a-uuid",
            "/api/v1/sales/invoices/{invoice_id}",
            None,
        ),
        (
            "GET",
            "/api/v1/purchases/not-a-uuid",
            "/api/v1/purchases/{purchase_id}",
            None,
        ),
        (
            "GET",
            "/api/v1/gst/einvoice/not-a-uuid",
            "/api/v1/gst/einvoice/{invoice_id}",
            None,
        ),
    ],
)
def test_documented_vs_runtime_validation_schema_consistency(
    client: TestClient,
    test_app: FastAPI,
    method: str,
    request_path: str,
    schema_path: str,
    payload: dict[str, Any] | None,
) -> None:
    """Documented OpenAPI 400 schema covers runtime validation payloads."""
    # 1. Execute runtime request with invalid inputs
    req_kwargs: dict[str, Any] = {"json": payload} if payload is not None else {}
    response = client.request(method, request_path, **req_kwargs)

    # 2. Assert runtime status code is 400
    assert response.status_code == HTTP_BAD_REQUEST

    # 3. Assert runtime payload matches ValidationErrorResponse
    body = response.json()
    model = ValidationErrorResponse.model_validate(body)
    assert model.success is False
    assert model.message == "Request validation failed"
    assert model.data is not None
    assert len(model.data) > 0

    # 4. Resolve operation schema in actual configured application
    openapi_schema = test_app.openapi()
    operation = openapi_schema["paths"][schema_path][method.lower()]
    assert "400" in operation["responses"]

    schema_400 = (
        operation["responses"]["400"]["content"]["application/json"]["schema"]
    )

    # 5. Verify the documented 400 schema covers ValidationErrorResponse
    if "$ref" in schema_400:
        assert schema_400["$ref"] == VAL_RESP_REF
    else:
        assert "anyOf" in schema_400
        refs = [item["$ref"] for item in schema_400["anyOf"] if "$ref" in item]
        assert VAL_RESP_REF in refs


def test_all_documented_400_operations_reference_canonical_schemas() -> None:
    """Every operation documenting HTTP 400 references canonical schemas."""
    schema = prod_app.openapi()
    checked_operations = 0

    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if isinstance(operation, dict) and "responses" in operation:
                responses = operation["responses"]
                if "400" in responses:
                    checked_operations += 1
                    content = responses["400"].get("content", {})
                    assert "application/json" in content, (
                        f"Missing application/json in 400 response for {method} {path}"
                    )
                    schema_obj = content["application/json"].get("schema", {})
                    if "$ref" in schema_obj:
                        assert schema_obj["$ref"] == VAL_RESP_REF
                    elif "anyOf" in schema_obj:
                        refs = {
                            item.get("$ref")
                            for item in schema_obj["anyOf"]
                            if isinstance(item, dict)
                        }
                        assert VAL_RESP_REF in refs, (
                            f"{VAL_RESP_REF} missing from anyOf in {method} {path}"
                        )
                        assert refs <= {VAL_RESP_REF, ERR_RESP_REF}, (
                            f"Unexpected refs in {method} {path}: {refs}"
                        )
                    else:
                        raise AssertionError(
                            f"Invalid 400 schema in {method} {path}: {schema_obj}"
                        )

    # Verify that all 106 operations with 400 were checked
    assert checked_operations == TOTAL_EXPECTED_400_OPERATIONS


def test_openapi_schema_contains_zero_422_responses(client: TestClient) -> None:
    """OpenAPI schema contains zero HTTP 422 responses across all routes."""
    schema = client.get("/openapi.json").json()

    found_422: list[str] = []
    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if (
                isinstance(operation, dict)
                and "responses" in operation
                and "422" in operation["responses"]
            ):
                found_422.append(f"{method.upper()} {path}")

    assert found_422 == []


def test_openapi_schema_documents_validation_error_responses(
    client: TestClient,
) -> None:
    """OpenAPI schema documents HTTP 400 and eliminates HTTPValidationError."""
    schema = client.get("/openapi.json").json()
    schemas = schema.get("components", {}).get("schemas", {})

    assert "HTTPValidationError" not in schemas
    assert "ValidationError" not in schemas
    assert "ValidationErrorResponse" in schemas
    assert "ValidationErrorItem" in schemas

    paths = schema.get("paths", {})
    assert "/api/v1/identity/register" in paths
    register_op = paths["/api/v1/identity/register"]["post"]
    assert "400" in register_op["responses"]

    assert "/api/v1/inventory/products" in paths
    get_products_op = paths["/api/v1/inventory/products"]["get"]
    assert "400" in get_products_op["responses"]
    schema_ref = (
        get_products_op["responses"]["400"]["content"]["application/json"]
        ["schema"]["$ref"]
    )
    assert schema_ref == VAL_RESP_REF
