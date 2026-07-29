"""Assistant request schemas."""

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssistantMessageRequest(BaseModel):
    """Request to send a user message to the assistant."""

    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID = Field(
        description="Business context the assistant must operate within.",
        examples=["6d75aecd-113d-4f5f-82bf-7c99eae4c5d4"],
    )
    message: str = Field(
        min_length=1,
        max_length=8000,
        description="User message for the assistant.",
        examples=["Summarize my current business context."],
    )
    conversation_id: uuid.UUID | None = Field(
        default=None,
        description="Existing conversation identifier. Omit to start a conversation.",
        examples=["9f16f47d-8b25-4f1a-bf56-f2cb60a04b19"],
    )
    language: str = Field(
        default="en",
        min_length=2,
        max_length=16,
        description="Conversation language hint.",
        examples=["en"],
    )
    timezone: str = Field(
        default="Asia/Calcutta",
        min_length=1,
        max_length=80,
        description="Conversation timezone hint.",
        examples=["Asia/Calcutta"],
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        """Reject blank user messages after trimming whitespace."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Message cannot be blank")
        return normalized
