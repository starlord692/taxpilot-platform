"""Assistant provider gateway exceptions."""

from http import HTTPStatus

from app.common.exceptions import TaxPilotException


class AssistantProviderGatewayException(TaxPilotException):
    """Raised when provider gateway execution fails."""

    status_code = HTTPStatus.BAD_GATEWAY
    error_code = "assistant.provider_gateway_failed"


class AssistantModelPolicyException(TaxPilotException):
    """Raised when model policy blocks provider execution."""

    status_code = HTTPStatus.FORBIDDEN
    error_code = "assistant.model_policy_denied"


class AssistantProviderResponseValidationException(TaxPilotException):
    """Raised when provider output is malformed or unsafe."""

    status_code = HTTPStatus.BAD_GATEWAY
    error_code = "assistant.provider_response_invalid"
