"""Global exception handling for the API."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.exceptions import TaxPilotException
from app.core.logging import get_logger
from app.core.responses import (
    ErrorDetail,
    ErrorResponse,
    ValidationErrorItem,
    ValidationErrorResponse,
)

logger = get_logger(__name__)

HTTP_STATUS_ERROR_CODES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_408_REQUEST_TIMEOUT: "request_timeout",
    status.HTTP_409_CONFLICT: "conflict",
    422: "validation_error",
    status.HTTP_429_TOO_MANY_REQUESTS: "too_many_requests",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
    status.HTTP_502_BAD_GATEWAY: "bad_gateway",
    status.HTTP_503_SERVICE_UNAVAILABLE: "service_unavailable",
    status.HTTP_504_GATEWAY_TIMEOUT: "gateway_timeout",
}


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
        error_code = HTTP_STATUS_ERROR_CODES.get(
            exc.status_code,
            f"http_{exc.status_code}",
        )
        response = ErrorResponse(
            success=False,
            message=str(exc.detail),
            data=ErrorDetail(code=error_code, details={}),
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
        response = ValidationErrorResponse(
            success=False,
            message="Request validation failed",
            data=[
                ValidationErrorItem(
                    loc=list(error.get("loc", ())),
                    msg=str(error.get("msg", "")),
                    type=str(error.get("type", "")),
                )
                for error in exc.errors()
            ],
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=response.model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("unhandled_exception", extra={"path": request.url.path})
        response = ErrorResponse(
            success=False,
            message="Internal server error",
            data=ErrorDetail(code="internal_error", details={}),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response.model_dump(),
        )
