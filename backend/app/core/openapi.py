"""OpenAPI contract helpers."""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

ERROR_RESPONSE_REF = {"$ref": "#/components/schemas/ErrorResponse"}


def configure_openapi(app: FastAPI) -> None:
    """Install TaxPilot's OpenAPI normalization hook."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            summary=app.summary,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
            servers=app.servers,
            terms_of_service=app.terms_of_service,
            contact=app.contact,
            license_info=app.license_info,
            separate_input_output_schemas=app.separate_input_output_schemas,
        )
        normalize_error_responses(schema)
        app.openapi_schema = schema
        return app.openapi_schema

    # FastAPI exposes app.openapi as the supported schema override hook.
    app.openapi = custom_openapi  # type: ignore[method-assign]


def normalize_error_responses(schema: dict[str, Any]) -> None:
    """Align generated error response docs with TaxPilot's runtime handlers."""
    for path_item in schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            responses = operation.setdefault("responses", {})
            if not isinstance(responses, dict):
                continue
            _replace_validation_response(responses)
            _document_common_error_response(responses, "500", "Internal server error.")


def _replace_validation_response(responses: dict[str, Any]) -> None:
    """Document request validation as the runtime 400 response."""
    validation_response = responses.pop("422", None)
    if validation_response is None and "400" in responses:
        return
    description = "Request validation failed."
    if isinstance(validation_response, dict):
        description = str(validation_response.get("description") or description)
    _document_common_error_response(responses, "400", description)


def _document_common_error_response(
    responses: dict[str, Any],
    status_code: str,
    description: str,
) -> None:
    """Add an ErrorResponse schema for a status code if one is not documented."""
    existing = responses.get(status_code)
    if isinstance(existing, dict) and "content" in existing:
        return
    responses[status_code] = {
        "description": (
            existing.get("description", description)
            if isinstance(existing, dict)
            else description
        ),
        "content": {
            "application/json": {
                "schema": ERROR_RESPONSE_REF,
            }
        },
    }