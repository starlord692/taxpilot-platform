"""Document request and response schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.documents.models import DocumentType, ExtractionStatus


class DocumentUploadRequest(BaseModel):
    """Service-level request for uploading a document."""

    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID = Field(description="Business UUID.")
    uploaded_by: uuid.UUID = Field(description="Uploading user UUID.")
    original_filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Original filename.",
        examples=["invoice.pdf"],
    )
    mime_type: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Document MIME type.",
        examples=["application/pdf"],
    )
    document_type: DocumentType = Field(
        default=DocumentType.UNKNOWN,
        description="Document classification.",
        examples=[DocumentType.SALES_INVOICE],
    )

    @field_validator("original_filename")
    @classmethod
    def normalize_filename(cls, value: str) -> str:
        """Normalize filename input."""
        filename = value.strip()
        if not filename:
            raise ValueError("original_filename is required")
        return filename

    @field_validator("mime_type")
    @classmethod
    def normalize_mime_type(cls, value: str) -> str:
        """Normalize MIME type input."""
        return value.strip().lower()


class OCRProcessRequest(BaseModel):
    """Request for OCR processing."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(
        default="default",
        min_length=2,
        max_length=100,
        description="OCR provider name.",
        examples=["default", "tesseract", "easyocr"],
    )
    language: str | None = Field(
        default=None,
        max_length=20,
        description="Preferred OCR language.",
        examples=["eng"],
    )


class DocumentPageResponse(BaseModel):
    """Response schema for document page metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Document page UUID.")
    document_id: uuid.UUID = Field(description="Document UUID.")
    page_number: int = Field(description="One-based page number.")
    storage_path: str | None = Field(default=None, description="Page storage path.")


class OCRResultResponse(BaseModel):
    """Response schema for OCR result metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="OCR result UUID.")
    document_id: uuid.UUID = Field(description="Document UUID.")
    page_number: int = Field(description="One-based page number.")
    provider: str = Field(description="OCR provider name.")
    language: str | None = Field(default=None, description="Detected language.")
    raw_text: str = Field(description="Raw OCR text.")
    confidence_score: Decimal = Field(description="OCR confidence score.")
    processing_time_ms: int = Field(description="OCR processing time in milliseconds.")


class DocumentResponse(BaseModel):
    """Full document response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Document UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    uploaded_by: uuid.UUID = Field(description="Uploader UUID.")
    original_filename: str = Field(description="Original filename.")
    mime_type: str = Field(description="MIME type.")
    file_size: int = Field(description="Stored file size in bytes.")
    storage_path: str = Field(description="Storage path.")
    checksum: str = Field(description="SHA-256 checksum.")
    document_type: DocumentType = Field(description="Document classification.")
    status: ExtractionStatus = Field(description="Document processing status.")
    page_count: int = Field(description="Document page count.")
    uploaded_at: datetime = Field(description="Upload timestamp.")
    processed_at: datetime | None = Field(
        default=None,
        description="OCR completion timestamp.",
    )
    pages: list[DocumentPageResponse] = Field(
        default_factory=list,
        description="Document pages.",
    )
    ocr_results: list[OCRResultResponse] = Field(
        default_factory=list,
        description="OCR results.",
    )


class DocumentListResponse(BaseModel):
    """Compact document list response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Document UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    original_filename: str = Field(description="Original filename.")
    mime_type: str = Field(description="MIME type.")
    file_size: int = Field(description="Stored file size in bytes.")
    document_type: DocumentType = Field(description="Document classification.")
    status: ExtractionStatus = Field(description="Document processing status.")
    page_count: int = Field(description="Document page count.")
    uploaded_at: datetime = Field(description="Upload timestamp.")
    processed_at: datetime | None = Field(
        default=None,
        description="OCR completion timestamp.",
    )
