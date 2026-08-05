"""Deterministic assembly service for authoritative Business Momentum output.

The service validates and assembles supplied direction, relative-rate context, and
observed change. It does not infer movement, calculate direction or rate, apply
policy, retrieve data, persist results, call AI, or expose an API.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.business_momentum.models import (
    BusinessMomentumAssessment,
    DeterministicChangeEvidence,
    MomentumDirection,
    ObservedBusinessChange,
)


@dataclass(frozen=True, slots=True)
class BusinessMomentumAssessmentInput:
    """Authoritative input used to assemble one Momentum assessment."""

    business_id: uuid.UUID
    assessed_at: datetime
    direction: MomentumDirection
    evidence: tuple[DeterministicChangeEvidence, ...]
    observed_changes: tuple[ObservedBusinessChange, ...] = ()
    relative_rate: str | None = None
    applied_policy_reference: str | None = None
    limitations: tuple[str, ...] = ()


class BusinessMomentumService:
    """Assemble validated Business Momentum from authoritative input only."""

    def assemble(
        self,
        assessment_input: BusinessMomentumAssessmentInput,
    ) -> BusinessMomentumAssessment:
        """Return immutable output without determining movement or rate."""
        self._validate_observation_timing(assessment_input)
        return BusinessMomentumAssessment(
            business_id=assessment_input.business_id,
            assessed_at=assessment_input.assessed_at,
            direction=assessment_input.direction,
            evidence=assessment_input.evidence,
            observed_changes=assessment_input.observed_changes,
            relative_rate=assessment_input.relative_rate,
            applied_policy_reference=assessment_input.applied_policy_reference,
            limitations=assessment_input.limitations,
        )

    @staticmethod
    def _validate_observation_timing(
        assessment_input: BusinessMomentumAssessmentInput,
    ) -> None:
        """Ensure supplied evidence was observed no later than its assessment."""
        if any(
            evidence.observed_to > assessment_input.assessed_at
            for evidence in assessment_input.evidence
        ):
            raise ValueError("momentum evidence cannot end after the assessment time")
