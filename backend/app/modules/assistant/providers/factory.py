"""Assistant provider adapter factory."""

from app.modules.assistant.gateway.exceptions import AssistantModelPolicyException
from app.modules.assistant.providers.interface import AssistantProvider
from app.modules.assistant.providers.mock import MockAssistantProvider


class AssistantProviderFactory:
    """Create configured assistant provider adapters."""

    def create(self, *, provider_name: str, model_name: str) -> AssistantProvider:
        """Return a provider adapter for the configured provider/model."""
        normalized = provider_name.strip().lower()
        if normalized == "mock":
            provider = MockAssistantProvider()
            if model_name and model_name != provider.model_name:
                raise AssistantModelPolicyException(
                    "Configured assistant model does not match mock provider",
                    details={
                        "configured_model": model_name,
                        "expected_model": provider.model_name,
                    },
                )
            return provider
        raise AssistantModelPolicyException(
            "Assistant provider is not registered",
            details={"provider_name": provider_name},
        )
