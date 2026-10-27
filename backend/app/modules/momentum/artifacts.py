"""Immutable in-memory canonical Momentum artifact boundary.

The identity is supplied by the approved producer context. This fixture does
not invent a production identity formula or persistence technology.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CanonicalMomentumAssessment:
    """Immutable canonical assessment shape used by domain tests."""

    assessment_identity: str
    business_id: UUID
    assessment_created_at: datetime
    direction: str
    rate: str
    current_context: str
    comparison_context: str
    predecessor_assessment_identity: str | None = None


class InMemoryMomentumAssessmentStore:
    """Business-scoped insert-only store for controlled domain tests."""

    def __init__(self, assessments: Iterable[CanonicalMomentumAssessment] = ()) -> None:
        self._items: dict[tuple[UUID, str], CanonicalMomentumAssessment] = {}
        for assessment in assessments:
            self.publish(assessment)

    def publish(self, assessment: CanonicalMomentumAssessment) -> None:
        key = (assessment.business_id, assessment.assessment_identity)
        if key in self._items:
            raise ValueError("Canonical Momentum assessments are immutable")
        if assessment.predecessor_assessment_identity is not None:
            predecessor_key = (
                assessment.business_id,
                assessment.predecessor_assessment_identity,
            )
            if predecessor_key not in self._items:
                raise ValueError("Assessment predecessor is not in the same business")
        self._items[key] = assessment

    def get(
        self,
        *,
        business_id: UUID,
        assessment_identity: str,
    ) -> CanonicalMomentumAssessment | None:
        return self._items.get((business_id, assessment_identity))

    def history(self, *, business_id: UUID) -> tuple[CanonicalMomentumAssessment, ...]:
        return tuple(
            sorted(
                (
                    item
                    for (scope, _), item in self._items.items()
                    if scope == business_id
                ),
                key=lambda item: (
                    item.assessment_created_at,
                    item.assessment_identity,
                ),
            )
        )

