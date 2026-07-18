"""GST module exceptions."""

from app.common.exceptions import ConflictException, NotFoundException


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
