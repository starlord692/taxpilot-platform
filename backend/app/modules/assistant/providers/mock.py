"""Deterministic mock assistant provider for AI-001."""

from app.modules.assistant.providers.interface import AssistantProvider
from app.modules.assistant.providers.schemas import (
    LLMMessage,
    LLMResponse,
    LLMToolCall,
    LLMToolDefinition,
    TokenUsage,
)


class MockAssistantProvider(AssistantProvider):
    """Local deterministic provider used until a real LLM adapter is configured."""

    provider_name = "mock"
    model_name = "taxpilot-mock-assistant-v1"

    async def select_tools(
        self,
        *,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
    ) -> list[LLMToolCall]:
        """Select the business-context tool for business-specific questions."""
        latest = messages[-1].content.lower() if messages else ""
        asks_for_context = any(
            word in latest for word in ("business", "context", "company")
        )
        has_context_tool = any(tool.name == "business.get_context" for tool in tools)
        if asks_for_context and has_context_tool:
            return [LLMToolCall(tool_name="business.get_context")]
        return []

    async def complete(
        self,
        *,
        messages: list[LLMMessage],
        tool_outputs: list[dict[str, object]],
    ) -> LLMResponse:
        """Return a deterministic, grounded response from available tool output."""
        latest = messages[-1].content if messages else ""
        business_context = self._find_tool_output(tool_outputs, "business.get_context")
        if business_context is not None:
            business_name = str(business_context.get("legal_name", "this business"))
            role = str(business_context.get("membership_role", "member"))
            content = (
                f"You are working in {business_name}. "
                f"Your current membership role is {role}."
            )
        else:
            content = (
                "I can help with TaxPilot workflows by using approved tools. "
                "For business-specific answers, I need an authorized tool result."
            )
        estimated_input = sum(len(message.content.split()) for message in messages)
        estimated_output = len(content.split())
        return LLMResponse(
            content=content,
            model_name=self.model_name,
            usage=TokenUsage(
                input_tokens=estimated_input + len(latest.split()),
                output_tokens=estimated_output,
            ),
        )

    def _find_tool_output(
        self,
        tool_outputs: list[dict[str, object]],
        tool_name: str,
    ) -> dict[str, object] | None:
        """Return one matching tool output payload."""
        for output in tool_outputs:
            if output.get("tool_name") == tool_name:
                result = output.get("result")
                if isinstance(result, dict):
                    return result
        return None


