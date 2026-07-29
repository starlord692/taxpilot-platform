"""Assistant module exceptions."""

from http import HTTPStatus

from app.common.exceptions import (
    NotFoundException,
    TaxPilotException,
    ValidationException,
)


class AssistantConversationNotFoundException(NotFoundException):
    """Raised when a conversation cannot be found in the current context."""

    error_code = "assistant.conversation_not_found"


class AssistantProviderException(TaxPilotException):
    """Raised when an assistant provider fails."""

    status_code = HTTPStatus.BAD_GATEWAY
    error_code = "assistant.provider_failed"


class AssistantToolNotFoundException(NotFoundException):
    """Raised when a requested assistant tool is not registered."""

    error_code = "assistant.tool_not_found"


class AssistantToolPermissionException(TaxPilotException):
    """Raised when an assistant tool is not permitted in the current context."""

    status_code = HTTPStatus.FORBIDDEN
    error_code = "assistant.tool_not_permitted"


class AssistantValidationException(ValidationException):
    """Raised when assistant input or state validation fails."""

    error_code = "assistant.validation_failed"
