"""Document module exceptions."""

from app.common.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)


class DocumentNotFoundException(NotFoundException):
    """Raised when a document cannot be found."""

    error_code = "document.not_found"


class DuplicateDocumentException(ConflictException):
    """Raised when an uploaded document checksum already exists."""

    error_code = "document.duplicate_checksum"


class DocumentValidationException(ValidationException):
    """Raised when document validation fails."""

    error_code = "document.validation_failed"


class OCRProviderNotFoundException(NotFoundException):
    """Raised when an OCR provider cannot be resolved."""

    error_code = "document.ocr_provider_not_found"


class OCRProcessingException(ValidationException):
    """Raised when OCR processing fails."""

    error_code = "document.ocr_failed"
