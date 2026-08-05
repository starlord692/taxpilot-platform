"""Deterministic structured explanations for authoritative Business Momentum."""

from dataclasses import dataclass

from app.modules.business_momentum.models import (
    BusinessMomentumAssessment,
    DeterministicChangeEvidence,
    MomentumDirection,
)
from app.modules.business_momentum.policy import (
    BusinessMomentumPolicyOutcome,
    MomentumPolicyObservedChange,
    RelativeRateContext,
)


@dataclass(frozen=True, slots=True)
class BusinessMomentumExplanation:
    """Immutable explanation preserving authoritative policy output exactly."""

    direction: MomentumDirection | None
    relative_rate_context: RelativeRateContext
    applied_policy_identifier: str
    applied_policy_version: str
    decisive_observed_changes: tuple[MomentumPolicyObservedChange, ...]
    contrary_observed_changes: tuple[MomentumPolicyObservedChange, ...]
    material_deterministic_evidence: tuple[DeterministicChangeEvidence, ...]
    limitations: tuple[str, ...]


class BusinessMomentumExplanationEngine:
    """Validate and compose structured Momentum explanation without evaluation."""

    def explain(
        self,
        *,
        assessment: BusinessMomentumAssessment,
        policy_outcome: BusinessMomentumPolicyOutcome,
    ) -> BusinessMomentumExplanation:
        """Return authoritative policy structures only; never calculate or narrate."""
        if assessment.direction is not policy_outcome.direction:
            raise ValueError("policy outcome direction must match assessment direction")
        assessment_evidence = set(assessment.evidence)
        policy_evidence = policy_outcome.material_deterministic_evidence
        if len(set(policy_evidence)) != len(policy_evidence):
            raise ValueError("policy outcome evidence must not be duplicated")
        if not set(policy_evidence).issubset(assessment_evidence):
            raise ValueError("policy outcome evidence must exist in assessment")
        changes = (
            policy_outcome.decisive_observed_changes
            + policy_outcome.contrary_observed_changes
        )
        if any(
            not set(change.evidence).issubset(set(policy_evidence))
            for change in changes
        ):
            raise ValueError(
                "policy outcome changes must remain traceable to policy evidence"
            )
        return BusinessMomentumExplanation(
            direction=policy_outcome.direction,
            relative_rate_context=policy_outcome.relative_rate_context,
            applied_policy_identifier=policy_outcome.applied_policy_identifier,
            applied_policy_version=policy_outcome.applied_policy_version,
            decisive_observed_changes=policy_outcome.decisive_observed_changes,
            contrary_observed_changes=policy_outcome.contrary_observed_changes,
            material_deterministic_evidence=policy_evidence,
            limitations=policy_outcome.limitations,
        )
