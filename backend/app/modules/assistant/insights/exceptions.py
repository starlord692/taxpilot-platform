"""Assistant insight exceptions."""

from app.modules.assistant.exceptions import AssistantValidationException


class AssistantInsightValidationException(AssistantValidationException):
    """Raised when an insight request cannot be generated safely."""

    error_code = "assistant.insight_validation_failed"
