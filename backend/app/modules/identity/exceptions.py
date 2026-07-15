"""Identity-specific exceptions."""

from http import HTTPStatus

from app.common.exceptions import ConflictException, TaxPilotException


class IdentityEmailAlreadyExistsException(ConflictException):
    """Raised when an identity email address already exists."""

    error_code = "identity.email_already_exists"


class AuthenticationInvalidCredentialsException(TaxPilotException):
    """Raised when authentication credentials are invalid."""

    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "authentication.invalid_credentials"


class AuthenticationEmailNotVerifiedException(TaxPilotException):
    """Raised when a pending account attempts authentication."""

    status_code = HTTPStatus.FORBIDDEN
    error_code = "authentication.email_not_verified"


class AuthenticationAccountLockedException(TaxPilotException):
    """Raised when a locked account attempts authentication."""

    status_code = HTTPStatus.LOCKED
    error_code = "authentication.account_locked"


class AuthenticationAccountDisabledException(TaxPilotException):
    """Raised when a disabled account attempts authentication."""

    status_code = HTTPStatus.FORBIDDEN
    error_code = "authentication.account_disabled"


class TokenConfigurationException(TaxPilotException):
    """Raised when token service configuration is invalid."""

    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code = "token.configuration_error"


class TokenExpiredException(TaxPilotException):
    """Raised when a token has expired."""

    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "token.expired"


class TokenInvalidException(TaxPilotException):
    """Raised when a token is malformed or has an invalid signature."""

    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "token.invalid"


class TokenRevokedException(TaxPilotException):
    """Raised when a refresh token has been revoked."""

    status_code = HTTPStatus.UNAUTHORIZED
    error_code = "token.revoked"
