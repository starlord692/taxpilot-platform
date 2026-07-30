"""Provider response validation for assistant gateway calls."""

from app.modules.assistant.gateway.exceptions import (
    AssistantProviderResponseValidationException,
)
from app.modules.assistant.gateway.schemas import ModelPolicy
from app.modules.assistant.providers.schemas import LLMResponse, LLMToolCall
from app.modules.assistant.tools import AssistantToolRegistry


class ProviderResponseValidator:
    """Validate untrusted provider responses before assistant consumption."""

    def validate_tool_calls(
        self,
        *,
        tool_calls: list[LLMToolCall],
        tool_registry: AssistantToolRegistry,
    ) -> list[str]:
        """Validate selected tool calls against the registered tool catalog."""
        findings: list[str] = []
        for tool_call in tool_calls:
            try:
                tool = tool_registry.get(tool_call.tool_name)
            except Exception as exc:
                raise AssistantProviderResponseValidationException(
                    "Provider selected an unregistered assistant tool",
                    details={"tool_name": tool_call.tool_name},
                ) from exc
            tool.input_model.model_validate(tool_call.arguments)
            findings.append(f"Tool call validated: {tool_call.tool_name}")
        return findings

    def validate_completion(
        self,
        *,
        response: LLMResponse,
        policy: ModelPolicy,
    ) -> list[str]:
        """Validate provider completion structure and usage bounds."""
        if not response.content.strip():
            raise AssistantProviderResponseValidationException(
                "Provider response content is empty",
            )
        if response.model_name != policy.model_name:
            raise AssistantProviderResponseValidationException(
                "Provider response model does not match selected model policy",
                details={
                    "expected_model": policy.model_name,
                    "actual_model": response.model_name,
                },
            )
        if response.usage.input_tokens > policy.max_input_tokens:
            raise AssistantProviderResponseValidationException(
                "Provider response exceeds input token policy",
            )
        if response.usage.output_tokens > policy.max_output_tokens:
            raise AssistantProviderResponseValidationException(
                "Provider response exceeds output token policy",
            )
        return ["Provider completion validated"]
