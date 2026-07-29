"""FastAPI application entrypoint for TaxPilot AI."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.database import dispose_database, initialize_database
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.openapi import configure_openapi
from app.core.responses import ApiResponse
from app.infrastructure.redis import close_redis, initialize_redis
from app.modules.assistant.api import router as assistant_router
from app.modules.business.api import router as business_router
from app.modules.catalog.api import router as catalog_router
from app.modules.documents.api import router as documents_router
from app.modules.expenses.api import router as expenses_router
from app.modules.gst.api import router as gst_router
from app.modules.identity.api.login_router import router as identity_login_router
from app.modules.identity.api.router import router as identity_router
from app.modules.identity.api.session_router import router as identity_session_router
from app.modules.identity.middleware import AuthenticationMiddleware
from app.modules.inventory.api import router as inventory_router
from app.modules.purchases.api import router as purchases_router
from app.modules.sales.api import router as sales_router
from app.modules.sales.api.payment_router import router as sales_payment_router

logger = get_logger(__name__)


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
        logger.info("application_started", extra={"environment": settings.environment})
        try:
            yield
        finally:
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
    configure_openapi(app)
    app.add_middleware(AuthenticationMiddleware)
    app.include_router(identity_router, prefix=active_settings.api_v1_prefix)
    app.include_router(identity_login_router, prefix=active_settings.api_v1_prefix)
    app.include_router(identity_session_router, prefix=active_settings.api_v1_prefix)
    app.include_router(assistant_router, prefix=active_settings.api_v1_prefix)
    app.include_router(business_router, prefix=active_settings.api_v1_prefix)
    app.include_router(catalog_router, prefix=active_settings.api_v1_prefix)
    app.include_router(documents_router, prefix=active_settings.api_v1_prefix)
    app.include_router(expenses_router, prefix=active_settings.api_v1_prefix)
    app.include_router(gst_router, prefix=active_settings.api_v1_prefix)
    app.include_router(inventory_router, prefix=active_settings.api_v1_prefix)
    app.include_router(purchases_router, prefix=active_settings.api_v1_prefix)
    app.include_router(sales_router, prefix=active_settings.api_v1_prefix)
    app.include_router(sales_payment_router, prefix=active_settings.api_v1_prefix)

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

    return app


app = create_app()
