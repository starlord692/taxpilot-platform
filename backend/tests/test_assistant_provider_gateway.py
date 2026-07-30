"""Tests for AI-006 assistant provider gateway governance."""

import uuid
from typing import cast

import pytest
from pydantic import ValidationError

from app.modules.assistant.gateway.exceptions import (
    AssistantModelPolicyException,
    AssistantProviderResponseValidationException,
)
from app.modules.assistant.gateway.redaction import ProviderPayloadRedactor
from app.modules.assistant.gateway.schemas import ProviderSafetyStatus
from app.modules.assistant.gateway.service import AssistantProviderGateway
from app.modules.assistant.providers import (
    AssistantProvider,
    LLMMessage,
    LLMResponse,
    LLMToolCall,
    LLMToolDefinition,
    MockAssistantProvider,
    TokenUsage,
)
from app.modules.assistant.providers.factory import AssistantProviderFactory
from app.modules.assistant.tools import AssistantToolRegistry, GetBusinessContextTool


class BadToolSelectionProvider:
    """Provider test double that selects an unregistered tool."""

    provider_name = "mock"
    model_name = "taxpilot-mock-assistant-v1"

    async def select_tools(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
    ) -> list[LLMToolCall]:
        """Return an invalid tool selection."""
        _ = messages
        _ = tools
        return [LLMToolCall(tool_name="unknown.tool", arguments={})]

    async def complete(
        self,
        *,
        messages: list[LLMMessage],
        tool_outputs: list[dict[str, object]],
    ) -> LLMResponse:
        """Return a structurally valid completion."""
        _ = messages
        _ = tool_outputs
        return LLMResponse(
            content="Provider response.",
            model_name=self.model_name,
            usage=TokenUsage(input_tokens=1, output_tokens=2),
        )


class UngroundedBusinessProvider:
    """Provider test double that returns unsupported business facts."""

    provider_name = "mock"
    model_name = "taxpilot-mock-assistant-v1"

    async def select_tools(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
    ) -> list[LLMToolCall]:
        """Select no tools."""
        _ = messages
        _ = tools
        return []

    async def complete(
        self,
        *,
        messages: list[LLMMessage],
        tool_outputs: list[dict[str, object]],
    ) -> LLMResponse:
        """Return an ungrounded business-specific response."""
        _ = messages
        _ = tool_outputs
        return LLMResponse(
            content="Your business revenue increased this month.",
            model_name=self.model_name,
            usage=TokenUsage(input_tokens=3, output_tokens=6),
        )


def build_gateway(provider: AssistantProvider) -> AssistantProviderGateway:
    """Build a gateway with the business-context tool registered."""
    registry = AssistantToolRegistry()
    registry.register(GetBusinessContextTool())
    return AssistantProviderGateway(
        provider=provider,
        tool_registry=registry,
        environment="testing",
    )


def test_provider_session_context_contains_immutable_audit_metadata() -> None:
    """Provider calls carry immutable metadata for telemetry and audit review."""
    gateway = build_gateway(MockAssistantProvider())
    conversation_id = uuid.uuid4()
    run_id = uuid.uuid4()

    context = gateway.create_session_context(
        prompt_version="assistant-context-v1",
        conversation_id=conversation_id,
        run_id=run_id,
    )

    assert context.provider_name == "mock"
    assert context.model_name == "taxpilot-mock-assistant-v1"
    assert context.policy_version == "assistant-model-policy-registry-v1"
    assert context.capability_version == "assistant-provider-capability-registry-v1"
    assert context.prompt_version == "assistant-context-v1"
    assert context.conversation_id == conversation_id
    assert context.run_id == run_id
    assert context.correlation_id
    with pytest.raises(ValidationError):
        context.__setattr__("model_name", "changed")


@pytest.mark.asyncio
async def test_gateway_validates_registered_tool_selection() -> None:
    """Registered tool selections pass through provider response validation."""
    gateway = build_gateway(MockAssistantProvider())
    session_context = gateway.create_session_context(
        prompt_version="assistant-context-v1",
        conversation_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
    )
    registry = AssistantToolRegistry()
    registry.register(GetBusinessContextTool())
    tools = [
        LLMToolDefinition.model_validate(definition.model_dump())
        for definition in registry.definitions()
    ]

    tool_calls = await gateway.select_tools(
        session_context=session_context,
        messages=[LLMMessage(role="user", content="What business context is active?")],
        tools=tools,
    )

    assert tool_calls[0].tool_name == "business.get_context"
    assert gateway.telemetry[-1].safety_status == ProviderSafetyStatus.SAFE


@pytest.mark.asyncio
async def test_gateway_rejects_unregistered_tool_selection() -> None:
    """Untrusted providers cannot invoke tools outside the registered catalog."""
    gateway = build_gateway(cast(AssistantProvider, BadToolSelectionProvider()))
    session_context = gateway.create_session_context(
        prompt_version="assistant-context-v1",
        conversation_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
    )

    with pytest.raises(AssistantProviderResponseValidationException):
        await gateway.select_tools(
            session_context=session_context,
            messages=[LLMMessage(role="user", content="Do something")],
            tools=[],
        )


@pytest.mark.asyncio
async def test_gateway_blocks_ungrounded_business_specific_completion() -> None:
    """Business-specific provider output must be grounded in tool results."""
    gateway = build_gateway(cast(AssistantProvider, UngroundedBusinessProvider()))
    session_context = gateway.create_session_context(
        prompt_version="assistant-context-v1",
        conversation_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
    )

    with pytest.raises(AssistantModelPolicyException):
        await gateway.complete(
            session_context=session_context,
            messages=[LLMMessage(role="user", content="How is my revenue?")],
            tool_outputs=[],
        )

    assert gateway.telemetry[-1].safety_status == ProviderSafetyStatus.BLOCKED


@pytest.mark.asyncio
async def test_gateway_allows_safe_refusal_without_tool_output() -> None:
    """Safe refusal text remains available when no authoritative tool output exists."""
    gateway = build_gateway(MockAssistantProvider())
    session_context = gateway.create_session_context(
        prompt_version="assistant-context-v1",
        conversation_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
    )

    response = await gateway.complete(
        session_context=session_context,
        messages=[LLMMessage(role="user", content="Hello")],
        tool_outputs=[],
    )

    assert "authorized tool result" in response.content
    assert (
        gateway.telemetry[-1].safety_status
        == ProviderSafetyStatus.SAFE_WITH_WARNINGS
    )


def test_payload_redactor_removes_sensitive_request_values() -> None:
    """Provider-boundary metadata redaction strips secret-like values."""
    redacted = ProviderPayloadRedactor().redact_mapping(
        {
            "token": "secret-token",
            "nested": {"password": "raw-password", "safe": "visible"},
        }
    )

    assert redacted["token"] == "[REDACTED]"
    assert redacted["nested"] == {"password": "[REDACTED]", "safe": "visible"}


def test_provider_factory_selects_configured_mock_provider() -> None:
    """Provider adapter selection is configuration-driven."""
    provider = AssistantProviderFactory().create(
        provider_name="mock",
        model_name="taxpilot-mock-assistant-v1",
    )

    assert provider.provider_name == "mock"
    assert provider.model_name == "taxpilot-mock-assistant-v1"
