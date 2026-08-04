"""Deterministic structured explanations for authoritative Business Health output.

This engine does not calculate Health, alter policy, generate narrative, produce
recommendations, call AI, access repositories, or depend on infrastructure.
"""

from dataclasses import dataclass

from app.modules.business_health.models import (
    BusinessHealthAssessment,
    HealthContributor,
    HealthDimension,
    HealthDimensionEvidence,
    HealthState,
)
from app.modules.business_health.policy import BusinessHealthPolicyOutcome


@dataclass(frozen=True, slots=True)
class BusinessHealthExplanation:
    """Structured, traceable explanation of an authoritative Health assessment."""

    state: HealthState
    applied_rule: str
    decisive_dimensions: tuple[HealthDimension, ...]
    material_contributors: tuple[HealthContributor, ...]
    dimension_evidence: tuple[HealthDimensionEvidence, ...]
    limitations: tuple[str, ...]


class BusinessHealthExplanationEngine:
    """Compose a deterministic explanation from authoritative output only."""

    def explain(
        self,
        *,
        assessment: BusinessHealthAssessment,
        policy_outcome: BusinessHealthPolicyOutcome,
    ) -> BusinessHealthExplanation:
        """Return a validated structured explanation without changing Health.

        The engine preserves authoritative facts in their original structures. It
        does not generate prose, opinions, recommendations, or policy decisions.
        """
        self._ensure_consistent_state(assessment, policy_outcome)
        self._ensure_known_dimensions(assessment, policy_outcome)
        self._ensure_known_contributors(assessment, policy_outcome)
        return BusinessHealthExplanation(
            state=assessment.state,
            applied_rule=policy_outcome.applied_rule,
            decisive_dimensions=policy_outcome.decisive_dimensions,
            material_contributors=policy_outcome.contributors,
            dimension_evidence=assessment.dimension_evidence,
            limitations=self._collect_limitations(assessment),
        )

    @staticmethod
    def _ensure_consistent_state(
        assessment: BusinessHealthAssessment,
        policy_outcome: BusinessHealthPolicyOutcome,
    ) -> None:
        """Ensure the explanation does not replace an authoritative state."""
        if policy_outcome.state is not assessment.state:
            raise ValueError("policy outcome state must match assessment state")

    @staticmethod
    def _ensure_known_dimensions(
        assessment: BusinessHealthAssessment,
        policy_outcome: BusinessHealthPolicyOutcome,
    ) -> None:
        """Ensure decisive dimensions remain part of the assessment evidence."""
        if len(set(policy_outcome.decisive_dimensions)) != len(
            policy_outcome.decisive_dimensions
        ):
            raise ValueError("policy outcome dimensions must not be duplicated")
        assessment_dimensions = {
            evidence.dimension for evidence in assessment.dimension_evidence
        }
        if not set(policy_outcome.decisive_dimensions).issubset(assessment_dimensions):
            raise ValueError("policy outcome dimensions must exist in assessment")

    @staticmethod
    def _ensure_known_contributors(
        assessment: BusinessHealthAssessment,
        policy_outcome: BusinessHealthPolicyOutcome,
    ) -> None:
        """Ensure material contributors remain traceable to assessment output."""
        if not set(policy_outcome.contributors).issubset(set(assessment.contributors)):
            raise ValueError("policy outcome contributors must exist in assessment")

    @staticmethod
    def _collect_limitations(
        assessment: BusinessHealthAssessment,
    ) -> tuple[str, ...]:
        """Preserve explicit assessment and dimension limitations in stable order."""
        limitations = list(assessment.limitations)
        for evidence in assessment.dimension_evidence:
            limitations.extend(evidence.limitations)
        return tuple(dict.fromkeys(limitations))
