"""Assistant response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assistant.models import (
    AssistantRunStatus,
    ConversationStatus,
    MessageRole,
    ToolCallStatus,
    ToolSideEffect,
)


class AssistantToolCallResponse(BaseModel):
    """Public audit details for an assistant tool call."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tool_name: str
    status: ToolCallStatus
    side_effect: ToolSideEffect
    required_business_context: bool
    latency_ms: int | None = None


class AssistantMessageResponse(BaseModel):
    """Assistant conversation message response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime


class AssistantRunResponse(BaseModel):
    """Assistant run audit response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: AssistantRunStatus
    prompt_version: str
    provider_name: str
    model_name: str
    input_tokens: int
    output_tokens: int
    latency_ms: int | None = None


class AssistantResponse(BaseModel):
    """Response returned after a user message is processed."""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: uuid.UUID
    message: AssistantMessageResponse
    run: AssistantRunResponse
    tool_calls: list[AssistantToolCallResponse] = Field(default_factory=list)


class AssistantConversationResponse(BaseModel):
    """Conversation details with current conversation-scoped memory."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    language: str
    timezone: str
    status: ConversationStatus
    created_at: datetime
    messages: list[AssistantMessageResponse] = Field(default_factory=list)
