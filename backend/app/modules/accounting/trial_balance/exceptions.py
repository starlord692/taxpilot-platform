"""Trial Balance exceptions."""

from http import HTTPStatus
from typing import Any

from app.common.exceptions import TaxPilotException


class TrialBalanceFutureDateException(TaxPilotException):
    """Raised when an as_of_date in the future is requested."""

    status_code: int = HTTPStatus.BAD_REQUEST
    error_code: str = "accounting.trial_balance_future_date"

    def __init__(
        self,
        message: str = "Trial balance cannot be calculated for a future date",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception."""
        super().__init__(message=message, details=details)
