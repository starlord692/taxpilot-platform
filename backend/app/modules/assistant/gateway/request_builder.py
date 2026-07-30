"""Provider request builder for assistant gateway calls."""

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assistant.gateway.redaction import ProviderPayloadRedactor
from app.modules.assistant.gateway.schemas import (
    ModelPolicy,
    ProviderCapability,
    ProviderSessionContext,
)
from app.modules.assistant.providers.schemas import LLMMessage, LLMToolDefinition


class ProviderRequestEnvelope(BaseModel):
    """Safe provider request envelope used for validation and telemetry."""

    model_config = ConfigDict(extra="forbid")

    session_context: ProviderSessionContext
    messages: list[LLMMessage]
    tools: list[LLMToolDefinition] = Field(default_factory=list)
    policy: ModelPolicy
    capability: ProviderCapability
    redacted_metadata: dict[str, object]


class ProviderRequestBuilder:
    """Build provider request envelopes without changing prompt semantics."""

    def __init__(self, redactor: ProviderPayloadRedactor | None = None) -> None:
        """Initialize with a provider-boundary redactor."""
        self._redactor = redactor or ProviderPayloadRedactor()

    def build(
        self,
        *,
        session_context: ProviderSessionContext,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        policy: ModelPolicy,
        capability: ProviderCapability,
    ) -> ProviderRequestEnvelope:
        """Return a provider request envelope with redacted audit metadata."""
        metadata = {
            "provider_name": session_context.provider_name,
            "model_name": session_context.model_name,
            "message_count": len(messages),
            "tool_count": len(tools),
            "policy_version": session_context.policy_version,
            "capability_version": session_context.capability_version,
        }
        return ProviderRequestEnvelope(
            session_context=session_context,
            messages=messages,
            tools=tools,
            policy=policy,
            capability=capability,
            redacted_metadata=self._redactor.redact_mapping(metadata),
        )
