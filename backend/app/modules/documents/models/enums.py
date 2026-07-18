"""Document processing enums."""

from enum import StrEnum


class DocumentType(StrEnum):
    """Supported document classifications."""

    UNKNOWN = "unknown"
    SALES_INVOICE = "sales_invoice"
    PURCHASE_INVOICE = "purchase_invoice"
    EXPENSE_RECEIPT = "expense_receipt"
    BANK_STATEMENT = "bank_statement"
    GST_CERTIFICATE = "gst_certificate"
    PAN = "pan"
    OTHER = "other"


class ExtractionStatus(StrEnum):
    """Supported OCR lifecycle statuses."""

    UPLOADED = "uploaded"
    OCR_PENDING = "ocr_pending"
    OCR_RUNNING = "ocr_running"
    OCR_COMPLETED = "ocr_completed"
    OCR_FAILED = "ocr_failed"
