"""Deterministic structured explanations for authoritative Business Confidence.

This engine preserves assessment coverage, deterministic evidence, approved
context, provenance, assessment time, and limitations. It does not calculate or
score confidence, implement policy, infer meaning, generate narrative or
recommendations, call AI, access repositories, or depend on infrastructure.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.business_confidence.models import (
    ApprovedConfidenceContext,
    BusinessConfidenceAssessment,
    BusinessUnderstandingCoverage,
)


@dataclass(frozen=True, slots=True)
class BusinessConfidenceExplanation:
    """Immutable structured preservation of one authoritative assessment."""

    assessment: BusinessConfidenceAssessment
    business_id: uuid.UUID
    assessed_at: datetime
    coverage: tuple[BusinessUnderstandingCoverage, ...]
    approved_context: tuple[ApprovedConfidenceContext, ...]
    limitations: tuple[str, ...]


class BusinessConfidenceExplanationEngine:
    """Validate and preserve one authoritative Confidence assessment only."""

    def explain(
        self,
        *,
        assessment: BusinessConfidenceAssessment,
    ) -> BusinessConfidenceExplanation:
        """Return immutable structures without calculation, policy, or narrative."""
        self._validate_assessment(assessment)
        return BusinessConfidenceExplanation(
            assessment=assessment,
            business_id=assessment.business_id,
            assessed_at=assessment.assessed_at,
            coverage=assessment.coverage,
            approved_context=assessment.approved_context,
            limitations=assessment.limitations,
        )

    @staticmethod
    def _validate_assessment(assessment: BusinessConfidenceAssessment) -> None:
        """Defensively preserve the assessment's traceability invariants."""
        areas = tuple(coverage.area for coverage in assessment.coverage)
        if len(set(areas)) != len(areas):
            raise ValueError(
                "confidence assessment coverage areas must not be duplicated"
            )
        if any(
            evidence.observed_at > assessment.assessed_at
            for coverage in assessment.coverage
            for evidence in coverage.evidence
        ):
            raise ValueError("confidence evidence cannot be observed after assessment")
        if any(
            context.effective_at > assessment.assessed_at
            for context in assessment.approved_context
        ):
            raise ValueError("confidence context cannot be effective after assessment")
