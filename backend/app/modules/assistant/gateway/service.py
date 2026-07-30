"""Assistant provider gateway service."""

import asyncio
import uuid

from app.common.models.abstract.timestamp import utc_now
from app.modules.assistant.gateway.exceptions import AssistantModelPolicyException
from app.modules.assistant.gateway.request_builder import ProviderRequestBuilder
from app.modules.assistant.gateway.response_validator import ProviderResponseValidator
from app.modules.assistant.gateway.safety import ProviderResponseSafetyChecker
from app.modules.assistant.gateway.schemas import (
    ModelPolicy,
    ProviderCallPhase,
    ProviderCapability,
    ProviderSafetyStatus,
    ProviderSessionContext,
    ProviderTelemetry,
)
from app.modules.assistant.gateway.telemetry import ProviderCallTimer
from app.modules.assistant.providers import AssistantProvider
from app.modules.assistant.providers.capabilities import ProviderCapabilityRegistry
from app.modules.assistant.providers.policies import ModelPolicyRegistry
from app.modules.assistant.providers.schemas import (
    LLMMessage,
    LLMResponse,
    LLMToolCall,
    LLMToolDefinition,
)
from app.modules.assistant.tools import AssistantToolRegistry


class AssistantProviderGateway:
    """Govern all assistant provider interactions."""

    def __init__(
        self,
        *,
        provider: AssistantProvider,
        tool_registry: AssistantToolRegistry,
        environment: str,
        model_policy_registry: ModelPolicyRegistry | None = None,
        capability_registry: ProviderCapabilityRegistry | None = None,
        request_builder: ProviderRequestBuilder | None = None,
        response_validator: ProviderResponseValidator | None = None,
        safety_checker: ProviderResponseSafetyChecker | None = None,
    ) -> None:
        """Initialize with provider adapter and governance registries."""
        self._provider = provider
        self._tool_registry = tool_registry
        self._environment = environment
        self._model_policies = model_policy_registry or ModelPolicyRegistry()
        self._capabilities = capability_registry or ProviderCapabilityRegistry()
        self._request_builder = request_builder or ProviderRequestBuilder()
        self._validator = response_validator or ProviderResponseValidator()
        self._safety = safety_checker or ProviderResponseSafetyChecker()
        self.telemetry: list[ProviderTelemetry] = []

    @property
    def provider_name(self) -> str:
        """Return the provider name stored in run audit records."""
        return self._provider.provider_name

    @property
    def model_name(self) -> str:
        """Return the model name stored in run audit records."""
        return self._provider.model_name

    def create_session_context(
        self,
        *,
        prompt_version: str,
        conversation_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> ProviderSessionContext:
        """Create immutable provider invocation metadata."""
        policy = self._policy()
        capability = self._capability()
        return ProviderSessionContext(
            provider_name=self.provider_name,
            model_name=self.model_name,
            policy_version=policy.policy_version,
            capability_version=capability.capability_version,
            prompt_version=prompt_version,
            conversation_id=conversation_id,
            run_id=run_id,
            correlation_id=str(uuid.uuid4()),
            created_at=utc_now(),
        )

    async def select_tools(
        self,
        *,
        session_context: ProviderSessionContext,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
    ) -> list[LLMToolCall]:
        """Select tools through policy, capability, and response validation."""
        policy = self._policy()
        capability = self._capability()
        self._validate_policy(policy)
        envelope = self._request_builder.build(
            session_context=session_context,
            messages=messages,
            tools=tools,
            policy=policy,
            capability=capability,
        )
        _ = envelope
        timer = ProviderCallTimer()
        tool_calls = await asyncio.wait_for(
            self._provider.select_tools(messages=messages, tools=tools),
            timeout=policy.timeout_ms / 1000,
        )
        findings = self._validator.validate_tool_calls(
            tool_calls=tool_calls,
            tool_registry=self._tool_registry,
        )
        safety_status = self._safety.assess_tool_selection(
            finding_count=len(findings),
        )
        self._record_telemetry(
            session_context=session_context,
            phase=ProviderCallPhase.TOOL_SELECTION,
            safety_status=safety_status,
            latency_ms=timer.elapsed_ms(),
            findings=findings,
        )
        return tool_calls

    async def complete(
        self,
        *,
        session_context: ProviderSessionContext,
        messages: list[LLMMessage],
        tool_outputs: list[dict[str, object]],
    ) -> LLMResponse:
        """Complete a response through policy, capability, and safety checks."""
        policy = self._policy()
        capability = self._capability()
        self._validate_policy(policy)
        self._request_builder.build(
            session_context=session_context,
            messages=messages,
            tools=[],
            policy=policy,
            capability=capability,
        )
        timer = ProviderCallTimer()
        response = await asyncio.wait_for(
            self._provider.complete(messages=messages, tool_outputs=tool_outputs),
            timeout=policy.timeout_ms / 1000,
        )
        findings = self._validator.validate_completion(
            response=response,
            policy=policy,
        )
        safety_status, safety_findings = self._safety.assess_completion(
            content=response.content,
            tool_output_count=len(tool_outputs),
            require_grounding=policy.require_grounding,
        )
        findings.extend(safety_findings)
        if safety_status == ProviderSafetyStatus.BLOCKED:
            self._record_telemetry(
                session_context=session_context,
                phase=ProviderCallPhase.COMPLETION,
                safety_status=safety_status,
                latency_ms=timer.elapsed_ms(),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                findings=findings,
            )
            raise AssistantModelPolicyException(
                "Provider response failed assistant safety policy",
                details={"findings": findings},
            )
        self._record_telemetry(
            session_context=session_context,
            phase=ProviderCallPhase.COMPLETION,
            safety_status=safety_status,
            latency_ms=timer.elapsed_ms(),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            findings=findings,
        )
        return response

    def _policy(self) -> ModelPolicy:
        """Return the active model policy."""
        return self._model_policies.get_policy(
            provider_name=self.provider_name,
            model_name=self.model_name,
        )

    def _capability(self) -> ProviderCapability:
        """Return the active provider capability."""
        return self._capabilities.get_capability(self.provider_name)

    def _validate_policy(self, policy: ModelPolicy) -> None:
        """Validate model policy against current environment."""
        if not policy.enabled:
            raise AssistantModelPolicyException("Assistant model policy is disabled")
        if (
            policy.allowed_environments
            and self._environment not in policy.allowed_environments
        ):
            raise AssistantModelPolicyException(
                "Assistant model policy is not enabled for this environment",
                details={"environment": self._environment},
            )

    def _record_telemetry(
        self,
        *,
        session_context: ProviderSessionContext,
        phase: ProviderCallPhase,
        safety_status: ProviderSafetyStatus,
        latency_ms: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        retry_count: int = 0,
        error_code: str | None = None,
        findings: list[str] | None = None,
    ) -> None:
        """Record safe in-memory provider telemetry for this gateway instance."""
        self.telemetry.append(
            ProviderTelemetry(
                session_context=session_context,
                phase=phase,
                safety_status=safety_status,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                retry_count=retry_count,
                error_code=error_code,
                findings=findings or [],
            )
        )
