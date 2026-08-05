"""Deterministic assembly service for authoritative Business Confidence.

The service validates and assembles authoritative deterministic inputs. It does
not infer confidence, calculate Health or Momentum, redefine Business DNA,
implement policy, retrieve data, persist results, call AI, or expose an API.
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
class BusinessConfidenceAssessmentInput:
    """Authoritative input used to assemble a Confidence assessment."""

    business_id: uuid.UUID
    assessed_at: datetime
    coverage: tuple[BusinessUnderstandingCoverage, ...]
    approved_context: tuple[ApprovedConfidenceContext, ...] = ()
    limitations: tuple[str, ...] = ()


class BusinessConfidenceService:
    """Assemble validated Business Confidence from authoritative inputs only."""

    def assemble(
        self,
        assessment_input: BusinessConfidenceAssessmentInput,
    ) -> BusinessConfidenceAssessment:
        """Return immutable output without deriving confidence or any other signal."""
        self._validate_authoritative_timing(assessment_input)
        return BusinessConfidenceAssessment(
            business_id=assessment_input.business_id,
            assessed_at=assessment_input.assessed_at,
            coverage=assessment_input.coverage,
            approved_context=assessment_input.approved_context,
            limitations=assessment_input.limitations,
        )

    @staticmethod
    def _validate_authoritative_timing(
        assessment_input: BusinessConfidenceAssessmentInput,
    ) -> None:
        """Ensure supplied evidence and context existed at assessment time."""
        if any(
            evidence.observed_at > assessment_input.assessed_at
            for coverage in assessment_input.coverage
            for evidence in coverage.evidence
        ):
            raise ValueError("confidence evidence cannot be observed after assessment")
        if any(
            context.effective_at > assessment_input.assessed_at
            for context in assessment_input.approved_context
        ):
            raise ValueError("confidence context cannot be effective after assessment")
