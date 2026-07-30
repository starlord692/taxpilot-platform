"""Model policy registry for assistant provider governance."""

from app.modules.assistant.gateway.schemas import (
    MODEL_POLICY_REGISTRY_VERSION,
    ModelPolicy,
    ProviderRetryPolicy,
)


class ModelPolicyRegistry:
    """Canonical registry of permitted assistant model policies."""

    version = MODEL_POLICY_REGISTRY_VERSION

    def __init__(self, policies: list[ModelPolicy] | None = None) -> None:
        """Initialize with default policies unless explicit policies are provided."""
        configured = policies or [
            ModelPolicy(
                key="mock.default",
                provider_name="mock",
                model_name="taxpilot-mock-assistant-v1",
                allowed_environments={
                    "development",
                    "testing",
                    "staging",
                    "production",
                },
                max_input_tokens=8_000,
                max_output_tokens=2_000,
                timeout_ms=30_000,
                retry_policy=ProviderRetryPolicy.NEVER,
                max_retries=0,
                cost_tier="local",
            )
        ]
        self._policies = {
            (policy.provider_name, policy.model_name): policy
            for policy in configured
        }

    def get_policy(self, *, provider_name: str, model_name: str) -> ModelPolicy:
        """Return the policy for a provider/model pair."""
        return self._policies[(provider_name, model_name)]
