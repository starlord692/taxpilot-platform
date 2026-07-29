"""Provider-neutral assistant model interface."""

from typing import Protocol

from app.modules.assistant.providers.schemas import (
    LLMMessage,
    LLMResponse,
    LLMToolCall,
    LLMToolDefinition,
)


class AssistantProvider(Protocol):
    """Vendor-neutral interface for assistant model providers."""

    @property
    def provider_name(self) -> str:
        """Return the provider name stored in run audit records."""
        ...

    @property
    def model_name(self) -> str:
        """Return the model name stored in run audit records."""
        ...

    async def select_tools(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
    ) -> list[LLMToolCall]:
        """Select permitted tools to ground the response."""
        ...

    async def complete(
        self,
        *,
        messages: list[LLMMessage],
        tool_outputs: list[dict[str, object]],
    ) -> LLMResponse:
        """Produce a final response from prompt messages and tool outputs."""
        ...
