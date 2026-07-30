"""Provider capability registry for assistant provider governance."""

from app.modules.assistant.gateway.schemas import (
    PROVIDER_CAPABILITY_REGISTRY_VERSION,
    ProviderCapability,
)


class ProviderCapabilityRegistry:
    """Canonical registry of assistant provider technical capabilities."""

    version = PROVIDER_CAPABILITY_REGISTRY_VERSION

    def __init__(self, capabilities: list[ProviderCapability] | None = None) -> None:
        """Initialize with default provider capabilities."""
        configured = capabilities or [
            ProviderCapability(
                provider_name="mock",
                adapter_name="MockAssistantProvider",
                supports_chat_completion=True,
                supports_tool_selection=True,
                supports_structured_output=True,
                supports_streaming=False,
                supports_json_mode=True,
                supports_token_usage=True,
                supports_timeout=True,
                supports_retry=False,
                supported_model_families=["taxpilot-mock"],
                maximum_context_window=8_000,
                default_timeout_ms=30_000,
            )
        ]
        self._capabilities = {
            capability.provider_name: capability for capability in configured
        }

    def get_capability(self, provider_name: str) -> ProviderCapability:
        """Return capabilities for one provider."""
        return self._capabilities[provider_name]
