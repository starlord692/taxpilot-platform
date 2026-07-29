"""Global exception handling for the API."""

from http import HTTPStatus

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.exceptions import TaxPilotException
from app.core.logging import get_logger
from app.core.responses import ErrorDetail, ErrorResponse

logger = get_logger(__name__)


HTTP_ERROR_CODES: dict[int, str] = {
    HTTPStatus.BAD_REQUEST: "http.bad_request",
    HTTPStatus.UNAUTHORIZED: "authentication.required",
    HTTPStatus.FORBIDDEN: "authorization.forbidden",
    HTTPStatus.NOT_FOUND: "http.not_found",
    HTTPStatus.METHOD_NOT_ALLOWED: "http.method_not_allowed",
    HTTPStatus.CONFLICT: "http.conflict",
    HTTPStatus.UNPROCESSABLE_ENTITY: "validation.request_invalid",
    HTTPStatus.INTERNAL_SERVER_ERROR: "internal.server_error",
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
            content=response.model_dump(mode="json"),
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
        response = ErrorResponse(
            success=False,
            message=str(exc.detail),
            data=ErrorDetail(
                code=HTTP_ERROR_CODES.get(exc.status_code, "http.error"),
                details={"status_code": exc.status_code},
            ),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.warning("validation_error", extra={"path": request.url.path})
        response = ErrorResponse(
            success=False,
            message="Request validation failed",
            data=ErrorDetail(
                code="validation.request_invalid",
                details={
                    "errors": [
                        {
                            "loc": error.get("loc", ()),
                            "msg": error.get("msg", ""),
                            "type": error.get("type", ""),
                        }
                        for error in exc.errors()
                    ],
                },
            ),
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=response.model_dump(mode="json"),
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
            data=ErrorDetail(code="internal.server_error"),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response.model_dump(mode="json"),
        )
