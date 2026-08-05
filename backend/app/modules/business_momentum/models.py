"""Immutable domain models for the deterministic Business Momentum capability.

These models preserve authoritative observed business change over time. They do
not calculate direction or rate, define policy rules, predict outcomes, access
persistence, call AI, or execute business actions.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class MomentumDirection(StrEnum):
    """Canonical observed movement directions defined by KP-004."""

    IMPROVING = "improving"
    WEAKENING = "weakening"
    BROADLY_UNCHANGED = "broadly_unchanged"


@dataclass(frozen=True, slots=True)
class DeterministicChangeEvidence:
    """Traceable deterministic evidence of business change across a time range."""

    source: str
    reference: str
    description: str
    observed_from: datetime
    observed_to: datetime

    def __post_init__(self) -> None:
        """Require meaningful provenance and a valid observed time range."""
        if not self.source.strip():
            raise ValueError("momentum evidence source must not be blank")
        if not self.reference.strip():
            raise ValueError("momentum evidence reference must not be blank")
        if not self.description.strip():
            raise ValueError("momentum evidence description must not be blank")
        if self.observed_from >= self.observed_to:
            raise ValueError("momentum evidence must span observed time")


@dataclass(frozen=True, slots=True)
class ObservedBusinessChange:
    """An evidence-backed observed change that may support a Momentum assessment."""

    statement: str
    evidence: tuple[DeterministicChangeEvidence, ...]

    def __post_init__(self) -> None:
        """Prevent untraceable observed-change statements from entering the model."""
        if not self.statement.strip():
            raise ValueError("observed business change statement must not be blank")
        if not self.evidence:
            raise ValueError("observed business change requires deterministic evidence")


@dataclass(frozen=True, slots=True)
class BusinessMomentumAssessment:
    """Authoritative deterministic assessment of observed business movement.

    The assessment is an immutable output model only. Determining direction and
    relative rate belongs to a future founder-approved deterministic policy.
    """

    business_id: uuid.UUID
    assessed_at: datetime
    direction: MomentumDirection
    evidence: tuple[DeterministicChangeEvidence, ...]
    observed_changes: tuple[ObservedBusinessChange, ...] = ()
    relative_rate: str | None = None
    applied_policy_reference: str | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Protect traceability and explicit unsupported-rate context."""
        if not self.evidence:
            raise ValueError("momentum assessment requires deterministic evidence")
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("momentum assessment limitations must not be blank")
        if self.relative_rate is not None and not self.relative_rate.strip():
            raise ValueError("momentum relative rate must not be blank")
        if self.relative_rate is None and not self.limitations:
            raise ValueError(
                "momentum assessment requires a relative rate or an explicit limitation"
            )
        if (
            self.applied_policy_reference is not None
            and not self.applied_policy_reference.strip()
        ):
            raise ValueError("momentum policy reference must not be blank")
        self._validate_observed_changes()

    def _validate_observed_changes(self) -> None:
        """Require all cited observed changes to use assessment evidence."""
        assessment_evidence = set(self.evidence)
        if any(
            not set(change.evidence).issubset(assessment_evidence)
            for change in self.observed_changes
        ):
            raise ValueError(
                "observed business changes must reference assessment evidence"
            )
