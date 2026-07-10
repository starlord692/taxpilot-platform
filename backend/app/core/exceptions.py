"""Global exception handling for the API."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.exceptions import TaxPilotException
from app.core.logging import get_logger
from app.core.responses import ApiResponse, ErrorDetail, ErrorResponse

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register application-wide exception handlers."""

    @app.exception_handler(TaxPilotException)
    async def taxpilot_exception_handler(
        request: Request,
        exc: TaxPilotException,
    ) -> JSONResponse:
        logger.warning(
            "application_exception",
            extra={"path": request.url.path, "error_code": exc.error_code},
        )
        response = ErrorResponse(
            success=False,
            message=exc.message,
            data=ErrorDetail(code=exc.error_code, details=exc.details),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        logger.warning(
            "http_exception",
            extra={"path": request.url.path, "status_code": exc.status_code},
        )
        response = ApiResponse[dict[str, object] | None](
            success=False,
            message=str(exc.detail),
            data=None,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.warning("validation_error", extra={"path": request.url.path})
        response = ApiResponse[list[dict[str, object]]](
            success=False,
            message="Request validation failed",
            data=[
                {
                    "loc": error.get("loc", ()),
                    "msg": error.get("msg", ""),
                    "type": error.get("type", ""),
                }
                for error in exc.errors()
            ],
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=response.model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("unhandled_exception", extra={"path": request.url.path})
        response = ApiResponse[None](
            success=False,
            message="Internal server error",
            data=None,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response.model_dump(),
        )
