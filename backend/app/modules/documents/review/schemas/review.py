"""Document review schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.documents.review.models import (
    ReviewDecisionType,
    ReviewStatus,
    ValidationCategory,
    ValidationSeverity,
)


class ManualFieldUpdate(BaseModel):
    """Manual field update request."""

    model_config = ConfigDict(extra="forbid")

    field_name: str = Field(..., min_length=1, max_length=100)
    new_value: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=3, max_length=255)


class DocumentReviewRequest(BaseModel):
    """Review decision request."""

    model_config = ConfigDict(extra="forbid")

    decision: ReviewDecisionType = Field(description="Review decision.")
    notes: str | None = Field(default=None, max_length=500)
    corrections: list[ManualFieldUpdate] = Field(default_factory=list)


class ValidationIssueResponse(BaseModel):
    """Validation issue response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    severity: ValidationSeverity
    category: ValidationCategory
    field_name: str
    message: str
    expected_value: str | None = None
    actual_value: str | None = None
    resolved: bool


class DocumentReviewResponse(BaseModel):
    """Document review response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    review_status: ReviewStatus
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    ready_for_automation: bool


class ReviewRevisionResponse(BaseModel):
    """Review revision response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    field_name: str
    old_value: str | None = None
    new_value: str
    changed_by: uuid.UUID
    changed_at: datetime
    reason: str


class ReviewDecisionResponse(BaseModel):
    """Review decision response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    decision: ReviewDecisionType
    decided_by: uuid.UUID
    decided_at: datetime
    notes: str | None = None


class DocumentValidationResponse(BaseModel):
    """Validation and review aggregate response."""

    document_id: uuid.UUID
    business_id: uuid.UUID
    issues: list[ValidationIssueResponse] = Field(default_factory=list)
    review: DocumentReviewResponse | None = None
    revisions: list[ReviewRevisionResponse] = Field(default_factory=list)
    decisions: list[ReviewDecisionResponse] = Field(default_factory=list)
    ready_for_automation: bool = False
