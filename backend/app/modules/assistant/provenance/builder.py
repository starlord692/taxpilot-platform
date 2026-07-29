"""Execution provenance helpers."""

from app.modules.assistant.planning import ExecutionPlan, ExecutionPlanStep


class ExecutionProvenanceBuilder:
    """Build compact provenance payloads for assistant execution audit records."""

    def for_plan(
        self,
        *,
        plan: ExecutionPlan,
        business_id: str,
        user_id: str,
        conversation_id: str,
        run_id: str,
        correlation_id: str,
    ) -> dict[str, object]:
        """Return provenance for a persisted execution plan."""
        return {
            "business_id": business_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "run_id": run_id,
            "plan_version": plan.plan_version,
            "planner_version": plan.planner_version,
            "normalization_version": plan.normalization_version,
            "prompt_version": plan.prompt_version,
            "context_version": plan.context_version,
            "correlation_id": correlation_id,
        }

    def for_step(
        self,
        *,
        plan: ExecutionPlan,
        step: ExecutionPlanStep,
        business_id: str,
        run_id: str,
        correlation_id: str,
    ) -> dict[str, object]:
        """Return provenance for a persisted execution step."""
        return {
            "business_id": business_id,
            "run_id": run_id,
            "tool_name": step.tool_name,
            "capability_name": step.manifest.capability_name,
            "tool_manifest_version": step.manifest.manifest_version,
            "plan_version": plan.plan_version,
            "planner_version": plan.planner_version,
            "normalization_version": plan.normalization_version,
            "prompt_version": plan.prompt_version,
            "context_version": plan.context_version,
            "correlation_id": correlation_id,
        }
