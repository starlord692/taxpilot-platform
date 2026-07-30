"""Assistant action schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assistant.actions.enums import (
    ActionReadinessStatus,
    AssistantActionStatus,
    AssistantActionType,
    ReadinessSeverity,
)
from app.modules.assistant.models import ApprovalLevel, ToolSideEffect

ACTION_MANIFEST_REGISTRY_VERSION = "assistant-action-manifest-registry-v1"
ACTION_CAPABILITY_REGISTRY_VERSION = "assistant-action-capability-registry-v1"
ACTION_READINESS_VALIDATOR_VERSION = "assistant-action-readiness-v1"
ACTION_PREVIEW_VERSION = "assistant-action-preview-v1"
ACTION_PROVENANCE_VERSION = "assistant-action-provenance-v1"


class ActionManifest(BaseModel):
    """Canonical definition of one supported assistant action."""

    model_config = ConfigDict(extra="forbid")

    action_type: AssistantActionType
    manifest_version: str = ACTION_MANIFEST_REGISTRY_VERSION
    description: str
    domain_owner: str
    required_service: str
    input_schema: dict[str, Any]
    required_permissions: list[str] = Field(default_factory=list)
    approval_level: ApprovalLevel = ApprovalLevel.EXPLICIT_USER_APPROVAL
    side_effect: ToolSideEffect = ToolSideEffect.WRITE
    idempotency_required: bool = True
    readiness_rules: list[str] = Field(default_factory=list)
    downstream_integrations: list[str] = Field(default_factory=list)
    result_record_type: str
    enabled: bool = True


class ActionCapability(BaseModel):
    """Technical execution capability for a supported assistant action."""

    model_config = ConfigDict(extra="forbid")

    action_type: AssistantActionType
    capability_version: str = ACTION_CAPABILITY_REGISTRY_VERSION
    adapter_name: str
    supports_preview: bool = True
    supports_idempotency: bool = True
    supports_approval_gate: bool = True
    supports_replay: bool = True
    max_payload_bytes: int = 16_384
    execution_timeout_ms: int = 30_000


class ReadinessFinding(BaseModel):
    """One readiness validation finding for an action draft."""

    model_config = ConfigDict(extra="forbid")

    severity: ReadinessSeverity
    code: str
    message: str
    field: str | None = None
    evidence: dict[str, object] = Field(default_factory=dict)
    blocking: bool = False


class ExecutionPreview(BaseModel):
    """User-facing summary of a pending assistant action before approval."""

    model_config = ConfigDict(extra="forbid")

    preview_version: str = ACTION_PREVIEW_VERSION
    action_type: AssistantActionType
    summary: str
    side_effect: ToolSideEffect
    approval_required: bool
    approval_level: ApprovalLevel
    downstream_integrations: list[str]
    readiness_status: ActionReadinessStatus
    readiness_findings: list[ReadinessFinding]
    idempotency_key: str


class ActionDraftCreate(BaseModel):
    """Input for creating an assistant action draft."""

    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID
    conversation_id: uuid.UUID
    run_id: uuid.UUID
    action_type: AssistantActionType
    draft_payload: dict[str, object]
    source: str = "assistant"


class ActionDraftResponse(BaseModel):
    """Serialized assistant action draft."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    business_id: uuid.UUID
    conversation_id: uuid.UUID
    run_id: uuid.UUID
    action_type: AssistantActionType
    manifest_version: str
    capability_version: str
    status: AssistantActionStatus
    draft_payload: dict[str, object]
    validated_payload: dict[str, object] | None
    readiness_status: ActionReadinessStatus
    readiness_findings: list[object]
    execution_preview: dict[str, object] | None
    approval_required: bool
    approval_level: ApprovalLevel
    approval_id: uuid.UUID | None
    idempotency_key: str
    provenance: dict[str, object]
    expires_at: datetime


class ActionResultResponse(BaseModel):
    """Serialized assistant action execution result."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    draft_id: uuid.UUID
    business_id: uuid.UUID
    erp_record_type: str | None
    erp_record_id: uuid.UUID | None
    domain_service: str
    status: str
    result_payload: dict[str, object]
    failure_reason: str | None
    completed_at: datetime | None
