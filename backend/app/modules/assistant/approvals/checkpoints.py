"""Assistant approval checkpoint policy."""

from datetime import timedelta

from app.common.models.abstract.timestamp import utc_now
from app.modules.assistant.models import ApprovalLevel, ApprovalStatus
from app.modules.assistant.planning import (
    ExecutionPlan,
    ExecutionPolicyResult,
    normalized_hash,
)

APPROVAL_TTL_MINUTES = 30


class ApprovalCheckpointService:
    """Create deterministic approval checkpoint payloads for execution plans."""

    def build_checkpoint(
        self,
        *,
        plan: ExecutionPlan,
        policy_result: ExecutionPolicyResult,
        business_id: str,
        requested_by: str,
    ) -> dict[str, object] | None:
        """Return a checkpoint payload when policy requires approval."""
        if policy_result.approval_level in {
            ApprovalLevel.NONE,
            ApprovalLevel.AUTO_ALLOWED,
        }:
            return None
        now = utc_now()
        plan_hash = normalized_hash(plan.model_dump(mode="json"))
        return {
            "business_id": business_id,
            "requested_by": requested_by,
            "approval_level": policy_result.approval_level,
            "status": ApprovalStatus.PENDING,
            "reason": "; ".join(policy_result.reasons) or "Approval required",
            "plan_hash": plan_hash,
            "provenance": {
                "source": "execution_policy",
                "plan_version": plan.plan_version,
                "planner_version": plan.planner_version,
                "normalization_version": plan.normalization_version,
            },
            "expires_at": now + timedelta(minutes=APPROVAL_TTL_MINUTES),
        }
