"""Document review enums."""

from enum import StrEnum


class ValidationSeverity(StrEnum):
    """Validation issue severity."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationCategory(StrEnum):
    """Validation issue category."""

    GST = "gst"
    PAN = "pan"
    TOTAL = "total"
    TAX = "tax"
    DUPLICATE = "duplicate"
    DATE = "date"
    CURRENCY = "currency"
    MANDATORY = "mandatory"
    MATCHING = "matching"


class ReviewStatus(StrEnum):
    """Human review status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CORRECTION_REQUESTED = "correction_requested"


class ReviewDecisionType(StrEnum):
    """Review decision types."""

    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CORRECTION = "request_correction"
