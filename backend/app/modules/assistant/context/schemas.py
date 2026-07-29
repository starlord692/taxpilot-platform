"""Assistant context intelligence schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assistant.models import (
    AssistantWorkflowStatus,
    AssistantWorkflowType,
    EntityResolutionConfidence,
)


class ContextProvenance(BaseModel):
    """Provenance metadata attached to stored context items."""

    model_config = ConfigDict(extra="forbid")

    source: str
    source_id: str | None = None
    source_version: str
    generated_by: str
    generated_at: datetime


class ActiveEntityContext(BaseModel):
    """Entity reference included in prompt context."""

    model_config = ConfigDict(extra="forbid")

    entity_type: str
    entity_id: uuid.UUID | None = None
    entity_label: str
    confidence: EntityResolutionConfidence
    confidence_score: float
    provenance: ContextProvenance


class WorkflowContext(BaseModel):
    """Conversation workflow context included in prompts."""

    model_config = ConfigDict(extra="forbid")

    workflow_type: AssistantWorkflowType
    status: AssistantWorkflowStatus
    current_step: str
    active_entity_refs: list[dict[str, object]] = Field(default_factory=list)
    pending_decisions: list[dict[str, object]] = Field(default_factory=list)
    expires_at: datetime
    provenance: ContextProvenance


class ToolOutputContext(BaseModel):
    """Recent authoritative tool output included in prompt context."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    result: dict[str, object]
    provenance: ContextProvenance


class ConversationContext(BaseModel):
    """Complete conversation-scoped context snapshot for one assistant run."""

    model_config = ConfigDict(extra="forbid")

    context_version: str
    business_id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID
    language: str
    timezone: str
    business_context: dict[str, object]
    conversation_summary: str | None = None
    active_workflow: WorkflowContext | None = None
    active_entities: list[ActiveEntityContext] = Field(default_factory=list)
    recent_tool_outputs: list[ToolOutputContext] = Field(default_factory=list)
    pending_decisions: list[dict[str, object]] = Field(default_factory=list)
    provenance: ContextProvenance

    def to_prompt_block(self, *, max_chars: int) -> str:
        """Render context in a deterministic provider-neutral prompt block."""
        payload = self.model_dump(mode="json")
        lines = [
            "TaxPilot conversation context follows.",
            "This context is conversation-scoped and not authoritative by itself.",
            "Tool outputs remain the only authoritative business-specific source.",
            str(payload),
        ]
        rendered = "\n".join(lines)
        if len(rendered) <= max_chars:
            return rendered
        return rendered[: max_chars - 40] + "\n[context truncated by policy]"
