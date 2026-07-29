"""Provider-neutral assistant completion schemas."""

from pydantic import BaseModel, ConfigDict, Field


class LLMMessage(BaseModel):
    """Provider-neutral prompt message."""

    model_config = ConfigDict(extra="forbid")

    role: str
    content: str


class LLMToolDefinition(BaseModel):
    """Provider-neutral tool capability manifest exposed to a model provider."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    input_schema: dict[str, object]
    output_schema: dict[str, object] = Field(default_factory=dict)
    capability_name: str | None = None
    required_permissions: list[str] = Field(default_factory=list)
    requires_business_context: bool
    approval_level: str = "none"
    side_effect: str
    idempotency_required: bool = False
    retry_policy: str = "never"
    timeout_ms: int = 30_000
    dependency_hints: list[str] = Field(default_factory=list)
    estimated_latency_ms: int | None = None
    estimated_cost: str | None = None
    authoritative_output_schema: dict[str, object] = Field(default_factory=dict)
    manifest_version: str = "assistant-tool-manifest-v1"


class LLMToolCall(BaseModel):
    """Provider-neutral tool call request."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)


class TokenUsage(BaseModel):
    """Provider-neutral token usage accounting."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int = 0
    output_tokens: int = 0


class LLMResponse(BaseModel):
    """Provider-neutral completion response."""

    model_config = ConfigDict(extra="forbid")

    content: str
    model_name: str
    usage: TokenUsage = Field(default_factory=TokenUsage)

