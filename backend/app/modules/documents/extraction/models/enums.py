"""Document extraction enums."""

from enum import StrEnum


class ExtractionRunStatus(StrEnum):
    """Supported structured extraction run statuses."""

    COMPLETED = "completed"
    FAILED = "failed"
    REVIEW_REQUIRED = "review_required"


class ExtractedFieldSource(StrEnum):
    """Supported extracted field sources."""

    RULE = "rule"
    AI = "ai"
    VALIDATION = "validation"
