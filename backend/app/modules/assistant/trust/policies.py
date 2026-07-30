"""Canonical trust policy registry for assistant audit reports."""

from app.modules.assistant.trust.schemas import (
    TRUST_POLICY_REGISTRY_VERSION,
    TrustPolicyDefinition,
    TrustPolicySeverity,
)


class TrustPolicyRegistry:
    """Registry of structural trust checks for assistant explainability."""

    version = TRUST_POLICY_REGISTRY_VERSION

    def __init__(self) -> None:
        """Initialize the canonical trust policy registry."""
        self._policies = {
            policy.key: policy
            for policy in [
                TrustPolicyDefinition(
                    key="business_context_required",
                    title="Business Context Required",
                    description=(
                        "Business-scoped assistant activity must require context."
                    ),
                    severity=TrustPolicySeverity.ERROR,
                    applies_to="tool_call",
                    remediation_hint="Ensure business tools require resolved context.",
                ),
                TrustPolicyDefinition(
                    key="business_context_resolved",
                    title="Business Context Resolved",
                    description="Audit access must be scoped to an active business.",
                    severity=TrustPolicySeverity.ERROR,
                    applies_to="report",
                    remediation_hint=(
                        "Resolve business context before producing reports."
                    ),
                ),
                TrustPolicyDefinition(
                    key="tool_outputs_required_for_business_facts",
                    title="Tool Outputs Required",
                    description="Business-specific responses should use tool outputs.",
                    severity=TrustPolicySeverity.WARNING,
                    applies_to="run",
                    remediation_hint="Use registered read tools for business facts.",
                ),
                TrustPolicyDefinition(
                    key="read_only_tool_respected",
                    title="Read-Only Tool Boundary",
                    description="Trust reports must not execute write-capable tools.",
                    severity=TrustPolicySeverity.ERROR,
                    applies_to="tool_call",
                    remediation_hint="Keep trust tooling read-only.",
                ),
                TrustPolicyDefinition(
                    key="write_tool_requires_policy_approval",
                    title="Write Tool Approval",
                    description="Consequential tools must require execution approval.",
                    severity=TrustPolicySeverity.ERROR,
                    applies_to="execution_plan",
                    remediation_hint="Require policy approval for write-capable plans.",
                ),
                TrustPolicyDefinition(
                    key="execution_plan_version_recorded",
                    title="Execution Version Recorded",
                    description=(
                        "Execution plans must record planner and plan versions."
                    ),
                    severity=TrustPolicySeverity.WARNING,
                    applies_to="execution_plan",
                    remediation_hint="Persist plan version metadata for every plan.",
                ),
                TrustPolicyDefinition(
                    key="prompt_version_recorded",
                    title="Prompt Version Recorded",
                    description="Assistant runs must record the prompt version.",
                    severity=TrustPolicySeverity.ERROR,
                    applies_to="run",
                    remediation_hint="Persist prompt versions on assistant runs.",
                ),
                TrustPolicyDefinition(
                    key="tool_manifest_version_recorded",
                    title="Tool Manifest Version Recorded",
                    description="Execution steps must record tool manifest versions.",
                    severity=TrustPolicySeverity.WARNING,
                    applies_to="execution_step",
                    remediation_hint="Persist manifest versions on execution steps.",
                ),
                TrustPolicyDefinition(
                    key="evidence_required_for_insights",
                    title="Insight Evidence Required",
                    description="Insight outputs must contain evidence references.",
                    severity=TrustPolicySeverity.ERROR,
                    applies_to="tool_output",
                    remediation_hint="Return evidence for all generated insights.",
                ),
                TrustPolicyDefinition(
                    key="confidence_score_present",
                    title="Confidence Score Present",
                    description="Insight outputs should expose confidence.",
                    severity=TrustPolicySeverity.WARNING,
                    applies_to="tool_output",
                    remediation_hint="Include confidence in insight outputs.",
                ),
                TrustPolicyDefinition(
                    key="tenant_scope_consistent",
                    title="Tenant Scope Consistent",
                    description=(
                        "Assistant audit rows must share the requested business."
                    ),
                    severity=TrustPolicySeverity.ERROR,
                    applies_to="report",
                    remediation_hint="Reject cross-tenant assistant audit access.",
                ),
                TrustPolicyDefinition(
                    key="approval_checkpoint_recorded_when_required",
                    title="Approval Checkpoint Recorded",
                    description="Plans requiring approval must have a checkpoint.",
                    severity=TrustPolicySeverity.ERROR,
                    applies_to="approval",
                    remediation_hint="Persist approval checkpoints for approval plans.",
                ),
                TrustPolicyDefinition(
                    key="failed_run_has_failure_reason",
                    title="Failed Run Reason Recorded",
                    description="Failed runs should contain a failure reason.",
                    severity=TrustPolicySeverity.WARNING,
                    applies_to="run",
                    remediation_hint="Persist a reason when assistant runs fail.",
                ),
            ]
        }

    def get(self, key: str) -> TrustPolicyDefinition:
        """Return one trust policy definition."""
        return self._policies[key]

    def all(self) -> list[TrustPolicyDefinition]:
        """Return all canonical trust policies."""
        return list(self._policies.values())
