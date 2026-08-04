"""Deterministic Business Health assessment service governed by ES-002.

The service consumes authoritative, evidence-backed dimension inputs. It does not
retrieve data, persist results, call AI, expose APIs, or execute business actions.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.business_health.models import (
    CANONICAL_HEALTH_DIMENSIONS,
    BusinessHealthAssessment,
    HealthAttention,
    HealthChange,
    HealthContributor,
    HealthDimension,
    HealthDimensionEvidence,
    HealthImprovementGuidance,
    HealthState,
)
from app.modules.business_health.policy import BusinessHealthPolicyEngine

CONCERN_STATES = frozenset({HealthState.WATCH, HealthState.AT_RISK})


@dataclass(frozen=True, slots=True)
class HealthDimensionInput:
    """Authoritative deterministic input supplied for one Health dimension."""

    dimension: HealthDimension
    state: HealthState
    evidence: HealthDimensionEvidence
    contributors: tuple[HealthContributor, ...]

    def __post_init__(self) -> None:
        """Keep supplied evidence and contributors within their dimension boundary."""
        if self.evidence.dimension is not self.dimension:
            raise ValueError("dimension input evidence must match its dimension")
        if any(
            contributor.dimension is not self.dimension
            for contributor in self.contributors
        ):
            raise ValueError("dimension input contributors must match its dimension")


@dataclass(frozen=True, slots=True)
class BusinessHealthAssessmentInput:
    """Authoritative inputs required to determine one whole-business assessment."""

    business_id: uuid.UUID
    assessed_at: datetime
    dimensions: tuple[HealthDimensionInput, ...]
    attention_items: tuple[HealthAttention, ...] = ()
    improvement_guidance: tuple[HealthImprovementGuidance, ...] = ()
    limitations: tuple[str, ...] = ()
    previous_state: HealthState | None = None
    change_explanation: str | None = None

    def __post_init__(self) -> None:
        """Require all canonical dimensions and explainable meaningful changes."""
        dimensions = tuple(item.dimension for item in self.dimensions)
        if set(dimensions) != CANONICAL_HEALTH_DIMENSIONS:
            raise ValueError(
                "assessment input must contain all canonical health dimensions"
            )
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("assessment input dimensions must not be duplicated")
        if self.previous_state is None and self.change_explanation is not None:
            raise ValueError("change explanation requires a previous health state")
        if self.previous_state is not None and not self.change_explanation:
            raise ValueError("previous health state requires a change explanation")
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("assessment input limitations must not be blank")


class BusinessHealthService:
    """Determine deterministic whole-business Health from authoritative inputs."""

    def __init__(
        self,
        *,
        policy_engine: BusinessHealthPolicyEngine | None = None,
    ) -> None:
        """Initialize the service with the approved deterministic policy engine."""
        self._policy_engine = policy_engine or BusinessHealthPolicyEngine()

    def assess(
        self,
        assessment_input: BusinessHealthAssessmentInput,
    ) -> BusinessHealthAssessment:
        """Return the authoritative current-condition assessment.

        Policy evaluation is deterministic and remains independent of repositories,
        infrastructure, AI, and source-domain retrieval.
        """
        policy_outcome = self._policy_engine.evaluate(assessment_input.dimensions)
        state = policy_outcome.state
        contributors = policy_outcome.contributors
        change = self._build_change(
            assessment_input=assessment_input,
            state=state,
            contributors=contributors,
        )
        self._ensure_concern_guidance(
            state=state,
            attention_items=assessment_input.attention_items,
            improvement_guidance=assessment_input.improvement_guidance,
        )
        return BusinessHealthAssessment(
            business_id=assessment_input.business_id,
            assessed_at=assessment_input.assessed_at,
            state=state,
            dimension_evidence=tuple(
                dimension.evidence for dimension in assessment_input.dimensions
            ),
            contributors=contributors,
            change=change,
            attention_items=assessment_input.attention_items,
            improvement_guidance=assessment_input.improvement_guidance,
            limitations=assessment_input.limitations,
        )

    @staticmethod
    def _build_change(
        *,
        assessment_input: BusinessHealthAssessmentInput,
        state: HealthState,
        contributors: tuple[HealthContributor, ...],
    ) -> HealthChange | None:
        """Create an explainable change only when the whole-business state changed."""
        if assessment_input.previous_state is None:
            return None
        if assessment_input.previous_state is state:
            return None
        if not contributors:
            raise ValueError("a health state change requires material contributors")
        return HealthChange(
            previous_state=assessment_input.previous_state,
            current_state=state,
            explanation=assessment_input.change_explanation or "",
            contributors=contributors,
        )

    @staticmethod
    def _ensure_concern_guidance(
        *,
        state: HealthState,
        attention_items: tuple[HealthAttention, ...],
        improvement_guidance: tuple[HealthImprovementGuidance, ...],
    ) -> None:
        """Require advisory attention and guidance for material concern states."""
        if state not in CONCERN_STATES:
            return
        if not attention_items:
            raise ValueError("a health concern requires an attention item")
        if not improvement_guidance:
            raise ValueError("a health concern requires improvement guidance")
