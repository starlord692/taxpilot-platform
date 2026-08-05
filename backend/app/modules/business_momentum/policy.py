"""Deterministic Business Momentum policy evaluation governed by MOM-004 v1.0."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum, StrEnum

from app.modules.business_momentum.models import (
    DeterministicChangeEvidence,
    MomentumDirection,
)


class ObservedChangePolarity(StrEnum):
    """Source-domain classification of one observed change."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNCHANGED = "unchanged"


class EvidencePrecedence(IntEnum):
    """Approved conflict-resolution precedence, from highest to lowest."""

    TRUSTED_PLATFORM_AUTHORITY = 1
    OWNER_PUBLISHED_READ_MODEL = 2
    DETERMINISTIC_PROJECTION = 3


class RelativeRateContext(StrEnum):
    """Secondary policy context; never a Momentum Direction."""

    ACCELERATING = "accelerating"
    STEADY = "steady"
    MODERATING = "moderating"
    NOT_ESTABLISHED = "not_established"


@dataclass(frozen=True, slots=True)
class MomentumPolicyConfiguration:
    """Founder-approved, versioned deterministic evidence thresholds."""

    policy_identifier: str
    policy_version: str
    minimum_distinct_evidence_areas: int
    minimum_rate_evidence_areas: int

    def __post_init__(self) -> None:
        if not self.policy_identifier.strip() or not self.policy_version.strip():
            raise ValueError("momentum policy identifier and version must not be blank")
        if self.minimum_distinct_evidence_areas < 1:
            raise ValueError("momentum evidence threshold must be positive")
        if self.minimum_rate_evidence_areas < 1:
            raise ValueError("momentum rate evidence threshold must be positive")


@dataclass(frozen=True, slots=True)
class MomentumPolicyObservedChange:
    """Normalized authoritative change consumed by the Policy Engine."""

    evidence_area: str
    polarity: ObservedChangePolarity
    is_material: bool
    evidence_precedence: EvidencePrecedence
    statement: str
    evidence: tuple[DeterministicChangeEvidence, ...]
    relative_change_band: RelativeRateContext | None = None

    def __post_init__(self) -> None:
        if not self.evidence_area.strip() or not self.statement.strip():
            raise ValueError(
                "momentum policy change area and statement must not be blank"
            )
        if not self.evidence:
            raise ValueError("momentum policy change requires deterministic evidence")
        if self.relative_change_band is RelativeRateContext.NOT_ESTABLISHED:
            raise ValueError("not established is not an input relative change band")


@dataclass(frozen=True, slots=True)
class MomentumPolicyInput:
    """Authoritative normalized input for deterministic Momentum evaluation."""

    business_id: uuid.UUID
    assessed_at: datetime
    observed_changes: tuple[MomentumPolicyObservedChange, ...]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("momentum policy limitations must not be blank")


@dataclass(frozen=True, slots=True)
class BusinessMomentumPolicyOutcome:
    """Structured policy outcome with availability distinct from direction."""

    assessment_available: bool
    direction: MomentumDirection | None
    relative_rate_context: RelativeRateContext
    applied_policy_identifier: str
    applied_policy_version: str
    decisive_observed_changes: tuple[MomentumPolicyObservedChange, ...]
    contrary_observed_changes: tuple[MomentumPolicyObservedChange, ...]
    material_deterministic_evidence: tuple[DeterministicChangeEvidence, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.assessment_available != (self.direction is not None):
            raise ValueError("momentum availability must match direction presence")
        if not self.assessment_available and not self.limitations:
            raise ValueError("unavailable momentum requires explicit limitations")
        if (
            not self.assessment_available
            and self.relative_rate_context is not RelativeRateContext.NOT_ESTABLISHED
        ):
            raise ValueError("unavailable momentum rate must not be established")


@dataclass(frozen=True, slots=True)
class BusinessMomentumConflictResolution:
    """Resolved changes and blocking limitations from precedence evaluation."""

    resolved_changes: tuple[MomentumPolicyObservedChange, ...]
    blocking_limitations: tuple[str, ...]


class BusinessMomentumConflictResolver:
    """Resolve approved evidence-precedence conflicts without external dependencies."""

    def resolve(
        self,
        changes: tuple[MomentumPolicyObservedChange, ...],
    ) -> BusinessMomentumConflictResolution:
        """Apply precedence and retain equal-precedence conflicts as limitations."""
        resolved: list[MomentumPolicyObservedChange] = []
        limitations: list[str] = []
        for area in dict.fromkeys(change.evidence_area for change in changes):
            candidates = [change for change in changes if change.evidence_area == area]
            highest = min(change.evidence_precedence for change in candidates)
            selected = [
                change for change in candidates if change.evidence_precedence == highest
            ]
            if len({change.polarity for change in selected}) > 1:
                limitations.append(f"Unresolved equal-precedence conflict in {area}")
            else:
                resolved.extend(selected)
        return BusinessMomentumConflictResolution(
            resolved_changes=tuple(resolved),
            blocking_limitations=tuple(limitations),
        )


class BusinessMomentumPolicyEngine:
    """Evaluate approved deterministic Momentum policy without external dependencies."""

    def __init__(
        self,
        *,
        configuration: MomentumPolicyConfiguration,
        conflict_resolver: BusinessMomentumConflictResolver | None = None,
    ) -> None:
        self._configuration = configuration
        self._conflict_resolver = (
            conflict_resolver or BusinessMomentumConflictResolver()
        )

    def evaluate(
        self, policy_input: MomentumPolicyInput
    ) -> BusinessMomentumPolicyOutcome:
        """Return an explainable policy outcome from authoritative observed changes."""
        limitations = list(policy_input.limitations)
        if any(
            evidence.observed_to > policy_input.assessed_at
            for change in policy_input.observed_changes
            for evidence in change.evidence
        ):
            limitations.append("Evidence ends after the assessment time")
        conflict_resolution = self._conflict_resolver.resolve(
            policy_input.observed_changes
        )
        limitations.extend(conflict_resolution.blocking_limitations)
        resolved = conflict_resolution.resolved_changes
        areas = {change.evidence_area for change in resolved}
        if len(areas) < self._configuration.minimum_distinct_evidence_areas:
            limitations.append(
                "Approved deterministic evidence threshold is not satisfied"
            )
        if limitations:
            return self._unavailable(limitations)
        positive = tuple(
            change
            for change in resolved
            if change.is_material and change.polarity is ObservedChangePolarity.POSITIVE
        )
        negative = tuple(
            change
            for change in resolved
            if change.is_material and change.polarity is ObservedChangePolarity.NEGATIVE
        )
        if (
            len({item.evidence_area for item in positive})
            > len({item.evidence_area for item in negative})
            and len({item.evidence_area for item in positive})
            >= self._configuration.minimum_distinct_evidence_areas
        ):
            direction = MomentumDirection.IMPROVING
            decisive, contrary = positive, negative
        elif (
            len({item.evidence_area for item in negative})
            > len({item.evidence_area for item in positive})
            and len({item.evidence_area for item in negative})
            >= self._configuration.minimum_distinct_evidence_areas
        ):
            direction = MomentumDirection.WEAKENING
            decisive, contrary = negative, positive
        else:
            direction = MomentumDirection.BROADLY_UNCHANGED
            decisive, contrary = (
                (),
                tuple(item for item in resolved if item.is_material),
            )
        rate = self._determine_relative_rate(direction, decisive)
        return BusinessMomentumPolicyOutcome(
            assessment_available=True,
            direction=direction,
            relative_rate_context=rate,
            applied_policy_identifier=self._configuration.policy_identifier,
            applied_policy_version=self._configuration.policy_version,
            decisive_observed_changes=decisive,
            contrary_observed_changes=contrary,
            material_deterministic_evidence=tuple(
                e for item in resolved if item.is_material for e in item.evidence
            ),
            limitations=(),
        )

    def _unavailable(self, limitations: list[str]) -> BusinessMomentumPolicyOutcome:
        return BusinessMomentumPolicyOutcome(
            assessment_available=False,
            direction=None,
            relative_rate_context=RelativeRateContext.NOT_ESTABLISHED,
            applied_policy_identifier=self._configuration.policy_identifier,
            applied_policy_version=self._configuration.policy_version,
            decisive_observed_changes=(),
            contrary_observed_changes=(),
            material_deterministic_evidence=(),
            limitations=tuple(dict.fromkeys(limitations)),
        )

    def _determine_relative_rate(
        self,
        direction: MomentumDirection,
        decisive: tuple[MomentumPolicyObservedChange, ...],
    ) -> RelativeRateContext:
        if direction is MomentumDirection.BROADLY_UNCHANGED:
            return RelativeRateContext.NOT_ESTABLISHED
        bands = tuple(
            change.relative_change_band
            for change in decisive
            if change.relative_change_band is not None
        )
        if len(bands) < self._configuration.minimum_rate_evidence_areas:
            return RelativeRateContext.NOT_ESTABLISHED
        if (
            bands.count(RelativeRateContext.ACCELERATING)
            >= self._configuration.minimum_rate_evidence_areas
        ):
            return RelativeRateContext.ACCELERATING
        if (
            bands.count(RelativeRateContext.MODERATING)
            >= self._configuration.minimum_rate_evidence_areas
        ):
            return RelativeRateContext.MODERATING
        return RelativeRateContext.STEADY
