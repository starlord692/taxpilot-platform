"""Execution policy evaluation for assistant plans."""

from app.modules.assistant.models import (
    ApprovalLevel,
    ExecutionPolicyDecision,
    ToolSideEffect,
)
from app.modules.assistant.planning.schemas import ExecutionPlan, ExecutionPolicyResult


class ExecutionPolicyEvaluator:
    """Evaluate deterministic safety policy before tool execution."""

    def __init__(self, *, max_tool_count: int = 8) -> None:
        """Initialize with conservative execution limits."""
        self._max_tool_count = max_tool_count

    def evaluate(self, plan: ExecutionPlan) -> ExecutionPolicyResult:
        """Return the policy decision for a normalized plan."""
        reasons: list[str] = []
        if len(plan.steps) > self._max_tool_count:
            reasons.append("Execution plan exceeds maximum tool count")
            return ExecutionPolicyResult(
                decision=ExecutionPolicyDecision.BLOCKED,
                approval_level=ApprovalLevel.BLOCKED,
                reasons=reasons,
            )
        write_steps = [
            step
            for step in plan.steps
            if step.manifest.side_effect == ToolSideEffect.WRITE
        ]
        approval_level = ApprovalLevel.NONE
        for step in plan.steps:
            if step.manifest.approval_level == ApprovalLevel.BLOCKED:
                reasons.append(f"Tool is blocked by manifest: {step.tool_name}")
                return ExecutionPolicyResult(
                    decision=ExecutionPolicyDecision.BLOCKED,
                    approval_level=ApprovalLevel.BLOCKED,
                    reasons=reasons,
                )
            if step.manifest.approval_level in {
                ApprovalLevel.EXPLICIT_USER_APPROVAL,
                ApprovalLevel.ORGANIZATIONAL_APPROVAL,
            }:
                approval_level = step.manifest.approval_level
        if write_steps and approval_level == ApprovalLevel.NONE:
            approval_level = ApprovalLevel.EXPLICIT_USER_APPROVAL
        if approval_level in {
            ApprovalLevel.EXPLICIT_USER_APPROVAL,
            ApprovalLevel.ORGANIZATIONAL_APPROVAL,
        }:
            reasons.append("Execution plan contains consequential tool calls")
            return ExecutionPolicyResult(
                decision=ExecutionPolicyDecision.REQUIRES_APPROVAL,
                approval_level=approval_level,
                reasons=reasons,
            )
        return ExecutionPolicyResult(
            decision=ExecutionPolicyDecision.ALLOWED,
            approval_level=(
                ApprovalLevel.AUTO_ALLOWED if write_steps else ApprovalLevel.NONE
            ),
            reasons=reasons,
        )


