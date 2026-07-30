"""Schemas for assistant provider gateway governance."""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

MODEL_POLICY_REGISTRY_VERSION = "assistant-model-policy-registry-v1"
PROVIDER_CAPABILITY_REGISTRY_VERSION = "assistant-provider-capability-registry-v1"
PROVIDER_GATEWAY_VERSION = "assistant-provider-gateway-v1"
PROVIDER_RESPONSE_VALIDATOR_VERSION = "assistant-provider-response-validator-v1"
PROVIDER_SAFETY_VERSION = "assistant-provider-safety-v1"


class ProviderRetryPolicy(StrEnum):
    """Provider retry policies."""

    NEVER = "never"
    TRANSIENT_ONLY = "transient_only"


class ProviderSafetyStatus(StrEnum):
    """Safety status for a provider response."""

    SAFE = "safe"
    SAFE_WITH_WARNINGS = "safe_with_warnings"
    BLOCKED = "blocked"
    PROVIDER_FAILED = "provider_failed"


class ProviderCallPhase(StrEnum):
    """Provider call phase governed by the gateway."""

    TOOL_SELECTION = "tool_selection"
    COMPLETION = "completion"


class ProviderSessionContext(BaseModel):
    """Immutable request metadata for one provider invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_name: str
    model_name: str
    policy_version: str
    capability_version: str
    prompt_version: str
    conversation_id: uuid.UUID
    run_id: uuid.UUID
    correlation_id: str
    created_at: datetime


class ModelPolicy(BaseModel):
    """Governed model policy for provider execution."""

    model_config = ConfigDict(extra="forbid")

    key: str
    provider_name: str
    model_name: str
    allowed_environments: set[str] = Field(default_factory=set)
    max_input_tokens: int
    max_output_tokens: int
    timeout_ms: int
    retry_policy: ProviderRetryPolicy = ProviderRetryPolicy.NEVER
    max_retries: int = 0
    allow_business_context: bool = True
    require_grounding: bool = True
    enabled: bool = True
    cost_tier: str = "local"
    policy_version: str = MODEL_POLICY_REGISTRY_VERSION


class ProviderCapability(BaseModel):
    """Technical provider capability profile."""

    model_config = ConfigDict(extra="forbid")

    provider_name: str
    adapter_name: str
    supports_chat_completion: bool
    supports_tool_selection: bool
    supports_structured_output: bool
    supports_streaming: bool
    supports_json_mode: bool
    supports_token_usage: bool
    supports_timeout: bool
    supports_retry: bool
    supported_model_families: list[str]
    maximum_context_window: int
    default_timeout_ms: int
    capability_version: str = PROVIDER_CAPABILITY_REGISTRY_VERSION


class ProviderTelemetry(BaseModel):
    """Safe telemetry emitted for provider calls."""

    model_config = ConfigDict(extra="forbid")

    session_context: ProviderSessionContext
    phase: ProviderCallPhase
    safety_status: ProviderSafetyStatus
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    retry_count: int = 0
    error_code: str | None = None
    findings: list[str] = Field(default_factory=list)
