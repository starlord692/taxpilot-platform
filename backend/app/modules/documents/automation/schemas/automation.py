"""Document automation schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.documents.automation.models import AutomationState, AutomationType


class AutomationRequest(BaseModel):
    """Request to automate a reviewed document."""

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="Optional client supplied idempotency key.",
        examples=["doc-auto-INV-1001"],
    )


class AutomationRunResponse(BaseModel):
    """Automation run response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Automation run UUID.")
    document_id: uuid.UUID = Field(description="Document UUID.")
    business_id: uuid.UUID = Field(description="Business UUID.")
    automation_type: AutomationType = Field(description="Automation target type.")
    idempotency_key: str = Field(description="Automation idempotency key.")
    status: AutomationState = Field(description="Automation run status.")
    erp_record_type: str | None = Field(default=None, description="ERP record type.")
    erp_record_id: uuid.UUID | None = Field(
        default=None,
        description="ERP record UUID.",
    )
    started_at: datetime | None = Field(default=None, description="Start timestamp.")
    completed_at: datetime | None = Field(
        default=None,
        description="Completion timestamp.",
    )
    failure_reason: str | None = Field(default=None, description="Failure reason.")
    retry_count: int = Field(description="Retry count.")


class AutomationResult(BaseModel):
    """Automation orchestration result."""

    run: AutomationRunResponse
    reused_existing: bool = Field(
        default=False,
        description="Whether an existing completed run was returned.",
    )
