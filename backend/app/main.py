"""FastAPI application entrypoint for TaxPilot AI."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.common.outbox.relay import OutboxRelay
from app.common.outbox.subscribers import register_subscribers
from app.core.config import Settings, get_settings
from app.core.database import (
    dispose_database,
    get_session_factory,
    initialize_database,
)
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.responses import (
    ApiResponse,
    ValidationErrorItem,
    ValidationErrorResponse,
)
from app.infrastructure.redis import close_redis, initialize_redis
from app.modules.accounting.api import accounting_router
from app.modules.business.api import router as business_router
from app.modules.business_understanding.api import (
    router as business_understanding_router,
)
from app.modules.catalog.api import router as catalog_router
from app.modules.documents.api import router as documents_router
from app.modules.expenses.api import router as expenses_router
from app.modules.gst.api import router as gst_router
from app.modules.identity.api.login_router import router as identity_login_router
from app.modules.identity.api.router import router as identity_router
from app.modules.identity.api.session_router import router as identity_session_router
from app.modules.identity.middleware import AuthenticationMiddleware
from app.modules.inventory.api import router as inventory_router
from app.modules.momentum.api import router as momentum_router
from app.modules.purchases.api import router as purchases_router
from app.modules.sales.api import router as sales_router
from app.modules.sales.api.payment_router import router as sales_payment_router

logger = get_logger(__name__)

CORS_ALLOW_METHODS: list[str] = [
    "GET",
    "POST",
    "PUT",
    "DELETE",
    "PATCH",
    "OPTIONS",
]
CORS_ALLOW_HEADERS: list[str] = [
    "Authorization",
    "Content-Type",
    "Accept",
    "Origin",
    "X-Requested-With",
]


def build_lifespan(
    initialize_resources: bool = True,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """Build an application lifespan handler."""

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if not initialize_resources:
            yield
            return

        settings = get_settings()
        configure_logging(settings)
        initialize_database(settings)
        await initialize_redis(settings)
        outbox_relay: OutboxRelay | None = None
        if settings.outbox_relay_enabled:
            try:
                session_factory = get_session_factory()
                outbox_relay = OutboxRelay(
                    session_factory=session_factory,
                    batch_size=settings.outbox_relay_batch_size,
                    poll_interval_seconds=settings.outbox_relay_poll_interval_seconds,
                )
                register_subscribers(outbox_relay)
                outbox_relay.start()
            except Exception as exc:
                logger.warning(
                    "outbox_relay_startup_skipped",
                    extra={"error": str(exc)},
                )
        logger.info("application_started", extra={"environment": settings.environment})
        try:
            yield
        finally:
            if outbox_relay is not None:
                await outbox_relay.stop()
            await close_redis()
            await dispose_database()
            logger.info("application_stopped")

    return lifespan


def create_app(
    settings: Settings | None = None,
    *,
    initialize_resources: bool = True,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    active_settings = settings or get_settings()
    configure_logging(active_settings)

    app = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=build_lifespan(initialize_resources),
    )

    register_exception_handlers(app)
    if active_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=active_settings.cors_origins,
            allow_credentials=True,
            allow_methods=CORS_ALLOW_METHODS,
            allow_headers=CORS_ALLOW_HEADERS,
        )
    app.add_middleware(AuthenticationMiddleware)
    app.include_router(identity_router, prefix=active_settings.api_v1_prefix)
    app.include_router(identity_login_router, prefix=active_settings.api_v1_prefix)
    app.include_router(identity_session_router, prefix=active_settings.api_v1_prefix)
    app.include_router(business_router, prefix=active_settings.api_v1_prefix)
    app.include_router(
        business_understanding_router,
        prefix=active_settings.api_v1_prefix,
    )
    app.include_router(catalog_router, prefix=active_settings.api_v1_prefix)
    app.include_router(documents_router, prefix=active_settings.api_v1_prefix)
    app.include_router(expenses_router, prefix=active_settings.api_v1_prefix)
    app.include_router(gst_router, prefix=active_settings.api_v1_prefix)
    app.include_router(inventory_router, prefix=active_settings.api_v1_prefix)
    app.include_router(momentum_router, prefix=active_settings.api_v1_prefix)
    app.include_router(purchases_router, prefix=active_settings.api_v1_prefix)
    app.include_router(sales_router, prefix=active_settings.api_v1_prefix)
    app.include_router(sales_payment_router, prefix=active_settings.api_v1_prefix)
    app.include_router(accounting_router, prefix=active_settings.api_v1_prefix)

    @app.get(
        f"{active_settings.api_v1_prefix}/health",
        response_model=ApiResponse[dict[str, str]],
        tags=["Health"],
        summary="Check API health",
    )
    async def health_check() -> ApiResponse[dict[str, str]]:
        """Return the current platform health status."""
        return ApiResponse(
            success=True,
            message="TaxPilot API is healthy",
            data={
                "status": "UP",
                "version": active_settings.app_version,
                "environment": active_settings.environment,
            },
        )

    configure_openapi(app)
    return app


def configure_openapi(app: FastAPI) -> None:
    """Configure OpenAPI generation to enforce canonical error contracts."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
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
        )

        schemas = openapi_schema.setdefault("components", {}).setdefault("schemas", {})
        val_item_schema = ValidationErrorItem.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
        val_resp_schema = ValidationErrorResponse.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
        val_resp_defs = val_resp_schema.pop("$defs", {})
        schemas["ValidationErrorItem"] = val_item_schema
        schemas.update(val_resp_defs)
        schemas["ValidationErrorResponse"] = val_resp_schema

        val_resp_ref = "#/components/schemas/ValidationErrorResponse"
        err_resp_ref = "#/components/schemas/ErrorResponse"

        for path_item in openapi_schema.get("paths", {}).values():
            for operation in path_item.values():
                if isinstance(operation, dict) and "responses" in operation:
                    responses = operation["responses"]
                    if "422" in responses:
                        if "400" not in responses:
                            responses["400"] = {
                                "description": "Request validation failed.",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": val_resp_ref}
                                    }
                                },
                            }
                        else:
                            existing_content = responses["400"].get("content", {})
                            json_media = existing_content.get("application/json", {})
                            existing_schema = json_media.get("schema")
                            if (
                                existing_schema
                                and existing_schema.get("$ref") == err_resp_ref
                            ):
                                json_media["schema"] = {
                                    "anyOf": [
                                        {"$ref": val_resp_ref},
                                        {"$ref": err_resp_ref},
                                    ]
                                }
                        del responses["422"]

        schemas.pop("HTTPValidationError", None)
        schemas.pop("ValidationError", None)

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


app = create_app()
