"""Schemas for assistant trust and explainability reports."""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

TRUST_REPORT_VERSION = "assistant-trust-report-v1"
TRUST_POLICY_REGISTRY_VERSION = "assistant-trust-policy-registry-v1"
TRUST_SCORING_VERSION = "assistant-trust-scoring-v1"
TRUST_GROUNDING_VERSION = "assistant-grounding-v1"


class TrustGrade(StrEnum):
    """Human-readable trust score bands."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TrustPolicyStatus(StrEnum):
    """Evaluation result for one trust policy."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class TrustPolicySeverity(StrEnum):
    """Severity levels for trust policy findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class GroundingStatus(StrEnum):
    """Structural grounding classification for assistant output."""

    GROUNDED = "grounded"
    PARTIALLY_GROUNDED = "partially_grounded"
    UNGROUNDED = "ungrounded"
    NOT_APPLICABLE = "not_applicable"


class AuditTimelineEventType(StrEnum):
    """Assistant audit timeline event categories."""

    MESSAGE = "message"
    RUN = "run"
    EXECUTION_PLAN = "execution_plan"
    EXECUTION_STEP = "execution_step"
    TOOL_CALL = "tool_call"
    APPROVAL = "approval"
    CONTEXT = "context"


class TrustReportVersion(BaseModel):
    """Version metadata attached to every assistant trust report."""

    model_config = ConfigDict(extra="forbid")

    report_version: str = TRUST_REPORT_VERSION
    policy_registry_version: str = TRUST_POLICY_REGISTRY_VERSION
    scoring_version: str = TRUST_SCORING_VERSION
    grounding_version: str = TRUST_GROUNDING_VERSION


class TrustPolicyDefinition(BaseModel):
    """Canonical trust policy definition."""

    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    description: str
    severity: TrustPolicySeverity
    applies_to: str
    remediation_hint: str
    version: str = TRUST_POLICY_REGISTRY_VERSION


class TrustPolicyResult(BaseModel):
    """Evaluated trust policy result."""

    model_config = ConfigDict(extra="forbid")

    policy: TrustPolicyDefinition
    status: TrustPolicyStatus
    details: str


class AssistantTrustScore(BaseModel):
    """Structural trust score for one assistant report."""

    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0, le=1)
    grade: TrustGrade
    scoring_version: str = TRUST_SCORING_VERSION
    passed_checks: int
    warning_checks: int
    failed_checks: int
    limitations: list[str] = Field(default_factory=list)


class AssistantEvidenceReference(BaseModel):
    """One auditable reference used to ground assistant behavior."""

    model_config = ConfigDict(extra="forbid")

    source_type: str
    source_id: str | None = None
    source_label: str
    tool_name: str | None = None
    metric: str | None = None
    value: object | None = None
    generated_at: datetime | None = None


class AssistantEvidenceChain(BaseModel):
    """Chain of evidence available for assistant explanation."""

    model_config = ConfigDict(extra="forbid")

    evidence: list[AssistantEvidenceReference] = Field(default_factory=list)
    authoritative_tool_outputs: int
    limitations: list[str] = Field(default_factory=list)


class AssistantGroundingReport(BaseModel):
    """Structural grounding report for one assistant response."""

    model_config = ConfigDict(extra="forbid")

    status: GroundingStatus
    grounding_version: str = TRUST_GROUNDING_VERSION
    grounded_tool_outputs: int
    evidence_count: int
    findings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AssistantToolExecutionTrace(BaseModel):
    """Read-only trace for a persisted assistant tool call."""

    model_config = ConfigDict(extra="forbid")

    tool_call_id: uuid.UUID
    tool_name: str
    status: str
    side_effect: str
    required_business_context: bool
    input_payload: dict[str, object]
    output_payload: dict[str, object] | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AssistantExecutionStepTrace(BaseModel):
    """Read-only trace for a persisted execution step."""

    model_config = ConfigDict(extra="forbid")

    step_id: uuid.UUID
    step_order: int
    tool_name: str
    capability_name: str
    tool_manifest_version: str
    status: str
    side_effect: str
    required_business_context: bool
    idempotency_key: str
    latency_ms: int | None = None
    error_code: str | None = None
    failure_reason: str | None = None


class AssistantPolicyTrace(BaseModel):
    """Read-only execution policy trace."""

    model_config = ConfigDict(extra="forbid")

    plan_id: uuid.UUID | None = None
    policy_decision: str | None = None
    approval_level: str | None = None
    approval_status: str | None = None
    policy_reasons: list[object] = Field(default_factory=list)
    execution_mode: str | None = None
    idempotency_key: str | None = None
    correlation_id: str | None = None


class AssistantApprovalTrace(BaseModel):
    """Read-only approval checkpoint trace."""

    model_config = ConfigDict(extra="forbid")

    approval_id: uuid.UUID
    plan_id: uuid.UUID
    approval_level: str
    status: str
    reason: str
    requested_by: uuid.UUID
    approved_by: uuid.UUID | None = None
    expires_at: datetime
    decided_at: datetime | None = None


class AssistantAuditTimelineEntry(BaseModel):
    """One chronological assistant audit event."""

    model_config = ConfigDict(extra="forbid")

    occurred_at: datetime
    event_type: AuditTimelineEventType
    label: str
    reference_id: uuid.UUID
    status: str | None = None
    details: dict[str, object] = Field(default_factory=dict)


class AssistantRunExplanation(BaseModel):
    """Complete read-only explanation for one assistant run."""

    model_config = ConfigDict(extra="forbid")

    report_metadata: TrustReportVersion
    business_id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID
    run_id: uuid.UUID
    generated_at: datetime
    run_status: str
    prompt_version: str
    provider_name: str
    model_name: str
    policy_trace: AssistantPolicyTrace
    approval_traces: list[AssistantApprovalTrace]
    tool_timeline: list[AssistantToolExecutionTrace]
    execution_steps: list[AssistantExecutionStepTrace]
    evidence_chain: AssistantEvidenceChain
    grounding_report: AssistantGroundingReport
    policy_results: list[TrustPolicyResult]
    trust_score: AssistantTrustScore


class AssistantConversationAudit(BaseModel):
    """Read-only audit timeline for one assistant conversation."""

    model_config = ConfigDict(extra="forbid")

    report_metadata: TrustReportVersion
    business_id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID
    generated_at: datetime
    timeline: list[AssistantAuditTimelineEntry]
    run_count: int
    tool_call_count: int
    failed_run_count: int
    trust_score: AssistantTrustScore
