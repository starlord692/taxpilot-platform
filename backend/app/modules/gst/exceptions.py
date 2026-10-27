"""GST module exceptions."""

from app.common.exceptions import (
    ConflictException,
    InfrastructureException,
    NotFoundException,
    ValidationException,
)


class GSTRegistrationNotFoundException(NotFoundException):
    """Raised when a GST registration is not found."""

    error_code = "gst.registration_not_found"


class GSTTaxRateNotFoundException(NotFoundException):
    """Raised when a GST tax rate is not found."""

    error_code = "gst.tax_rate_not_found"


class GSTSettingsNotFoundException(NotFoundException):
    """Raised when GST settings are not found."""

    error_code = "gst.settings_not_found"


class GSTCodeNotFoundException(NotFoundException):
    """Raised when HSN or SAC code is not found."""

    error_code = "gst.code_not_found"


class GSTDuplicateRegistrationException(ConflictException):
    """Raised when active GST registration uniqueness is violated."""

    error_code = "gst.duplicate_registration"


class GSTDuplicateTaxRateException(ConflictException):
    """Raised when tax rate uniqueness is violated."""

    error_code = "gst.duplicate_tax_rate"


class GSTDuplicateSettingsException(ConflictException):
    """Raised when settings already exist for a business."""

    error_code = "gst.duplicate_settings"


class GSTINVerificationNotFoundException(NotFoundException):
    """Raised when a persistent GSTIN verification record is not found."""

    error_code = "gst.verification_not_found"


class GSTINDuplicateVerificationException(ConflictException):
    """Raised when verification record already exists for business and GSTIN."""

    error_code = "gst.duplicate_verification"


class GSTINInvalidStateTransitionException(ValidationException):
    """Raised when an illegal verification evidence state transition is attempted."""

    error_code = "gst.invalid_verification_state_transition"


class GSTINVerificationGatewayUnavailableException(InfrastructureException):
    """Raised when an external or mock verification gateway is unreachable."""

    error_code = "gst.verification_gateway_unavailable"


class GSTInvalidPeriodException(ValidationException):
    """Raised when an invalid tax period format or range is requested."""

    error_code = "gst.invalid_tax_period"


class GSTComparisonInputValidationException(ValidationException):
    """Raised when comparison inputs are contradictory, negative, or malformed."""

    error_code = "gst.invalid_comparison_input"

