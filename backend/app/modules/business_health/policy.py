"""Pure deterministic policy rules for Business Health.

The initial policy applies the founder-approved most-concerning-dimension rule.
It contains no repositories, infrastructure, persistence, AI, or scoring model.
"""

from dataclasses import dataclass
from typing import Protocol

from app.modules.business_health.models import (
    CANONICAL_HEALTH_DIMENSIONS,
    HealthContributor,
    HealthDimension,
    HealthState,
)

HEALTH_SEVERITY: dict[HealthState, int] = {
    HealthState.EXCELLENT: 0,
    HealthState.HEALTHY: 1,
    HealthState.STABLE: 2,
    HealthState.WATCH: 3,
    HealthState.AT_RISK: 4,
}
MOST_CONCERNING_DIMENSION_RULE = "most_concerning_canonical_dimension"


class HealthPolicyDimensionInput(Protocol):
    """Authoritative dimension state consumed by deterministic policy rules."""

    @property
    def dimension(self) -> HealthDimension:
        """Return the canonical Health dimension."""
        ...

    @property
    def state(self) -> HealthState:
        """Return the authoritative dimension state."""
        ...

    @property
    def contributors(self) -> tuple[HealthContributor, ...]:
        """Return evidence-backed contributors for the dimension."""
        ...


@dataclass(frozen=True, slots=True)
class BusinessHealthPolicyOutcome:
    """Explainable deterministic outcome of a Business Health policy evaluation."""

    state: HealthState
    applied_rule: str
    decisive_dimensions: tuple[HealthDimension, ...]
    contributors: tuple[HealthContributor, ...]


class BusinessHealthPolicyEngine:
    """Evaluate the approved initial deterministic Business Health policy."""

    def evaluate(
        self,
        dimensions: tuple[HealthPolicyDimensionInput, ...],
    ) -> BusinessHealthPolicyOutcome:
        """Determine state from the most concerning canonical dimension inputs.

        This is the approved initial implementation, not a permanent policy
        algorithm. The stable BusinessHealthService boundary can use a future
        deterministic Policy Engine without changing its consumers.
        """
        self._ensure_canonical_dimensions(dimensions)
        state = max(
            (dimension.state for dimension in dimensions),
            key=HEALTH_SEVERITY.__getitem__,
        )
        decisive_inputs = tuple(
            dimension for dimension in dimensions if dimension.state is state
        )
        return BusinessHealthPolicyOutcome(
            state=state,
            applied_rule=MOST_CONCERNING_DIMENSION_RULE,
            decisive_dimensions=tuple(
                dimension.dimension for dimension in decisive_inputs
            ),
            contributors=tuple(
                contributor
                for dimension in decisive_inputs
                for contributor in dimension.contributors
            ),
        )

    @staticmethod
    def _ensure_canonical_dimensions(
        dimensions: tuple[HealthPolicyDimensionInput, ...],
    ) -> None:
        """Prevent a departmental subset from becoming a Health policy input."""
        supplied = tuple(dimension.dimension for dimension in dimensions)
        if len(set(supplied)) != len(supplied):
            raise ValueError("policy input dimensions must not be duplicated")
        if set(supplied) != CANONICAL_HEALTH_DIMENSIONS:
            raise ValueError(
                "policy input must contain all canonical health dimensions"
            )
