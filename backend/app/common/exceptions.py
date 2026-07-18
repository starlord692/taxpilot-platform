"""Framework exception hierarchy for TaxPilot AI."""

from http import HTTPStatus
from typing import Any


class TaxPilotException(Exception):
    """Base exception for expected application errors."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize an application exception."""
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationException(TaxPilotException):
    """Raised when framework-level validation fails."""

    status_code = HTTPStatus.BAD_REQUEST
    error_code = "validation_error"


class NotFoundException(TaxPilotException):
    """Raised when a requested resource cannot be found."""

    status_code = HTTPStatus.NOT_FOUND
    error_code = "not_found"


class ConflictException(TaxPilotException):
    """Raised when an operation conflicts with current state."""

    status_code = HTTPStatus.CONFLICT
    error_code = "conflict"


class InfrastructureException(TaxPilotException):
    """Raised when an infrastructure dependency fails."""

    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    error_code = "infrastructure_error"
