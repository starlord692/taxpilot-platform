"""Execution planning schemas for assistant orchestration."""

from pydantic import BaseModel, ConfigDict, Field

from app.modules.assistant.models import (
    ApprovalLevel,
    ExecutionMode,
    ExecutionPolicyDecision,
    ToolRetryPolicy,
    ToolSideEffect,
)

PLAN_VERSION = "assistant-execution-plan-v1"
PLANNER_VERSION = "assistant-planner-v1"
NORMALIZATION_VERSION = "assistant-plan-normalizer-v1"
MANIFEST_VERSION = "assistant-tool-manifest-v1"


class ToolCapabilityManifest(BaseModel):
    """Deterministic execution metadata declared by a registered tool."""

    model_config = ConfigDict(extra="forbid")

    name: str
    capability_name: str
    description: str
    input_schema: dict[str, object]
    output_schema: dict[str, object] = Field(default_factory=dict)
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
    manifest_version: str = MANIFEST_VERSION


class ExecutionPlanStep(BaseModel):
    """Normalized tool step proposed for deterministic execution."""

    model_config = ConfigDict(extra="forbid")

    step_order: int
    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)
    dependencies: list[int] = Field(default_factory=list)
    manifest: ToolCapabilityManifest
    idempotency_key: str


class ExecutionPlan(BaseModel):
    """Versioned deterministic plan produced before tool execution."""

    model_config = ConfigDict(extra="forbid")

    plan_version: str = PLAN_VERSION
    planner_version: str = PLANNER_VERSION
    normalization_version: str = NORMALIZATION_VERSION
    prompt_version: str
    context_version: str
    execution_mode: ExecutionMode
    idempotency_key: str
    steps: list[ExecutionPlanStep]


class ExecutionPolicyResult(BaseModel):
    """Result of evaluating a normalized execution plan."""

    model_config = ConfigDict(extra="forbid")

    decision: ExecutionPolicyDecision
    approval_level: ApprovalLevel
    reasons: list[str] = Field(default_factory=list)
