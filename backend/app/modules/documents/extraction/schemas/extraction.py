"""Document extraction schemas."""

import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.documents.extraction.models import (
    ExtractedFieldSource,
    ExtractionRunStatus,
)
from app.modules.documents.models import DocumentType


class ExtractDocumentRequest(BaseModel):
    """Request schema for structured field extraction."""

    model_config = ConfigDict(extra="forbid")

    use_ai: bool = Field(
        default=True,
        description="Whether to use AI-assisted extraction after rule extraction.",
        examples=[True],
    )


class ExtractedFieldResponse(BaseModel):
    """Response schema for one extracted field."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Extracted field UUID.")
    document_id: uuid.UUID = Field(description="Document UUID.")
    field_name: str = Field(description="Field name.")
    field_value: str = Field(description="Extracted value.")
    confidence: Decimal = Field(description="Field confidence score.")
    source: ExtractedFieldSource = Field(description="Extraction source.")
    page_number: int = Field(description="Source page number.")
    bounding_box: dict[str, Any] | None = Field(
        default=None,
        description="Optional OCR bounding box.",
    )


class ExtractionReviewResponse(BaseModel):
    """Response schema for extraction review state."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Review UUID.")
    extracted_document_id: uuid.UUID = Field(description="Extracted document UUID.")
    reason: str = Field(description="Reason review is required.")
    notes: str | None = Field(default=None, description="Review notes.")
    resolved: bool = Field(description="Whether the review is resolved.")


class ExtractedDocumentResponse(BaseModel):
    """Response schema for structured document extraction output."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Extracted document UUID.")
    document_id: uuid.UUID = Field(description="Source document UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    document_type: DocumentType = Field(description="Classified document type.")
    overall_confidence: Decimal = Field(description="Overall extraction confidence.")
    status: ExtractionRunStatus = Field(description="Extraction run status.")
    review_required: bool = Field(description="Whether manual review is required.")
    fields: list[ExtractedFieldResponse] = Field(
        default_factory=list,
        description="Extracted structured fields.",
    )
    reviews: list[ExtractionReviewResponse] = Field(
        default_factory=list,
        description="Review records.",
    )
