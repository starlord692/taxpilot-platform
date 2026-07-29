"""Assistant tool contracts."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assistant.models import ApprovalLevel, ToolRetryPolicy, ToolSideEffect
from app.modules.business.api.context import BusinessContext
from app.modules.identity.models import IdentityUser


class EmptyToolInput(BaseModel):
    """Input model for tools that do not require arguments."""

    model_config = ConfigDict(extra="forbid")


class ToolContext(BaseModel):
    """Execution context passed to assistant tools."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    current_user: IdentityUser
    business_context: BusinessContext | None = None


class ToolDefinition(BaseModel):
    """Public assistant tool capability manifest."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    input_schema: dict[str, object]
    output_schema: dict[str, object] = Field(default_factory=dict)
    capability_name: str | None = None
    required_permissions: list[str] = Field(default_factory=list)
    requires_business_context: bool = True
    approval_level: ApprovalLevel = ApprovalLevel.NONE
    side_effect: ToolSideEffect = ToolSideEffect.READ
    idempotency_required: bool = False
    retry_policy: ToolRetryPolicy = ToolRetryPolicy.NEVER
    timeout_ms: int = 30_000
    dependency_hints: list[str] = Field(default_factory=list)
    estimated_latency_ms: int | None = None
    estimated_cost: str | None = None
    authoritative_output_schema: dict[str, object] = Field(default_factory=dict)
    manifest_version: str = "assistant-tool-manifest-v1"


class ToolResult(BaseModel):
    """Structured result returned by an assistant tool."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    result: dict[str, object]


class AssistantTool(Protocol):
    """Protocol implemented by permissioned assistant tools."""

    name: str
    description: str
    input_model: type[BaseModel]
    requires_business_context: bool
    side_effect: ToolSideEffect
    approval_level: ApprovalLevel
    idempotency_required: bool
    retry_policy: ToolRetryPolicy
    timeout_ms: int

    def definition(self) -> ToolDefinition:
        """Return provider-facing tool metadata."""
        ...

    async def execute(self, payload: BaseModel, context: ToolContext) -> ToolResult:
        """Execute the tool with validated input and context."""
        ...



