"""Pure, evidence-bound Business Momentum policy functions.

These helpers consume already-resolved Accounting evidence and do not access
Accounting persistence or derive source-domain semantics.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.modules.accounting.financial_performance_evidence.models import (
    BaselineEligibility,
    CurrencyCompatibility,
)


class ComparisonKind(StrEnum):
    PREVIOUS_COMPARABLE_PERIOD = "PREVIOUS_COMPARABLE_PERIOD"
    PRIOR_EQUIVALENT_PERIOD = "PRIOR_EQUIVALENT_PERIOD"
    APPROVED_ROLLING_WINDOW = "APPROVED_ROLLING_WINDOW"
    NO_VALID_COMPARISON = "NO_VALID_COMPARISON"


@dataclass(frozen=True)
class ComparisonCandidate:
    """Accounting-published candidate context supplied to Momentum."""

    kind: ComparisonKind
    comparable: bool
    available: bool = True
    rolling_authorized: bool = False


def select_comparison(
    candidates: Iterable[ComparisonCandidate],
) -> ComparisonKind:
    """Select the first valid context under MOM-COMPARISON-POLICY-001."""

    by_kind: dict[ComparisonKind, list[ComparisonCandidate]] = {}
    for candidate in candidates:
        by_kind.setdefault(candidate.kind, []).append(candidate)

    for kind in (
        ComparisonKind.PREVIOUS_COMPARABLE_PERIOD,
        ComparisonKind.PRIOR_EQUIVALENT_PERIOD,
        ComparisonKind.APPROVED_ROLLING_WINDOW,
    ):
        valid = [
            candidate
            for candidate in by_kind.get(kind, ())
            if candidate.available
            and candidate.comparable
            and (kind is not ComparisonKind.APPROVED_ROLLING_WINDOW
                 or candidate.rolling_authorized)
        ]
        if len(valid) == 1:
            return kind
        if len(valid) > 1:
            # The policy does not authorize an arbitrary tie-breaker.
            return ComparisonKind.NO_VALID_COMPARISON
    return ComparisonKind.NO_VALID_COMPARISON


class DimensionMovement(StrEnum):
    IMPROVING = "IMPROVING"
    DETERIORATING = "DETERIORATING"
    STABLE = "STABLE"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class WholeBusinessDirection(StrEnum):
    IMPROVING = "IMPROVING"
    DETERIORATING = "DETERIORATING"
    BROADLY_UNCHANGED = "BROADLY_UNCHANGED"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


def combine_direction(
    movements: Mapping[str, DimensionMovement],
) -> WholeBusinessDirection:
    """Apply the equal-dimension strict-majority direction policy."""

    valid = [
        movement
        for movement in movements.values()
        if movement is not DimensionMovement.INSUFFICIENT_INFORMATION
    ]
    if len(valid) < 3:  # noqa: PLR2004
        return WholeBusinessDirection.INSUFFICIENT_INFORMATION
    improving = valid.count(DimensionMovement.IMPROVING)
    deteriorating = valid.count(DimensionMovement.DETERIORATING)
    required = len(valid) // 2 + 1
    if improving >= required:
        return WholeBusinessDirection.IMPROVING
    if deteriorating >= required:
        return WholeBusinessDirection.DETERIORATING
    return WholeBusinessDirection.BROADLY_UNCHANGED


class RateClassification(StrEnum):
    GRADUAL = "GRADUAL"
    MODERATE = "MODERATE"
    RAPID = "RAPID"
    NOT_DETERMINABLE = "NOT_DETERMINABLE"


def classify_financial_performance_rate(
    *,
    current: Decimal | None,
    comparison: Decimal | None,
    baseline_eligibility: BaselineEligibility,
    currency_compatibility: CurrencyCompatibility,
    comparable: bool,
    evidence_valid: bool,
    stable: bool = False,
) -> RateClassification:
    """Classify a supplied Financial Performance movement, fail-closed.

    This function deliberately accepts already-derived values and Accounting
    baseline/currency determinations; it never computes source materiality or
    a near-zero threshold.
    """

    if (
        not evidence_valid
        or not comparable
        or current is None
        or comparison is None
        or currency_compatibility != CurrencyCompatibility.SAME_CURRENCY
        or baseline_eligibility != BaselineEligibility.ELIGIBLE
        or comparison == 0
        or current == 0 and comparison != 0
        or current * comparison < 0
        or stable
        or current == comparison
    ):
        return RateClassification.NOT_DETERMINABLE
    magnitude = abs(current - comparison) / abs(comparison)
    if magnitude < Decimal("0.10"):
        return RateClassification.GRADUAL
    if magnitude < Decimal("0.25"):
        return RateClassification.MODERATE
    return RateClassification.RAPID


def classify_field_movement(  # noqa: PLR0911
    *,
    field: str,
    current_amount: Decimal | None,
    comparison_amount: Decimal | None,
    materiality_outcome: str,
    currency_compatibility: CurrencyCompatibility,
    evidence_valid: bool = True,
    comparable: bool = True,
    materially_contradictory: bool = False,
) -> DimensionMovement:
    """Classify movement for a single AFPE field under MOM-FD-012."""

    if (
        not evidence_valid
        or not comparable
        or materially_contradictory
        or current_amount is None
        or comparison_amount is None
        or currency_compatibility != CurrencyCompatibility.SAME_CURRENCY
        or materiality_outcome == "UNDETERMINABLE"
    ):
        return DimensionMovement.INSUFFICIENT_INFORMATION

    if materiality_outcome == "NOT_MATERIAL":
        return DimensionMovement.STABLE

    if materiality_outcome == "MATERIAL":
        if field in ("period_revenue_total", "period_net_result"):
            if current_amount > comparison_amount:
                return DimensionMovement.IMPROVING
            if current_amount < comparison_amount:
                return DimensionMovement.DETERIORATING
            return DimensionMovement.STABLE

        if field == "period_expense_total":
            # Expense polarity is inverse to revenue/net result
            if current_amount < comparison_amount:
                return DimensionMovement.IMPROVING
            if current_amount > comparison_amount:
                return DimensionMovement.DETERIORATING
            return DimensionMovement.STABLE

    return DimensionMovement.INSUFFICIENT_INFORMATION


COHERENT_MOVEMENTS: dict[
    tuple[DimensionMovement, DimensionMovement, DimensionMovement],
    DimensionMovement,
] = {
    (
        DimensionMovement.IMPROVING,
        DimensionMovement.IMPROVING,
        DimensionMovement.IMPROVING,
    ): DimensionMovement.IMPROVING,
    (
        DimensionMovement.DETERIORATING,
        DimensionMovement.DETERIORATING,
        DimensionMovement.DETERIORATING,
    ): DimensionMovement.DETERIORATING,
    (
        DimensionMovement.STABLE,
        DimensionMovement.STABLE,
        DimensionMovement.STABLE,
    ): DimensionMovement.STABLE,
    (
        DimensionMovement.IMPROVING,
        DimensionMovement.STABLE,
        DimensionMovement.IMPROVING,
    ): DimensionMovement.IMPROVING,
    (
        DimensionMovement.STABLE,
        DimensionMovement.IMPROVING,
        DimensionMovement.IMPROVING,
    ): DimensionMovement.IMPROVING,
    (
        DimensionMovement.IMPROVING,
        DimensionMovement.DETERIORATING,
        DimensionMovement.IMPROVING,
    ): DimensionMovement.IMPROVING,
    (
        DimensionMovement.DETERIORATING,
        DimensionMovement.IMPROVING,
        DimensionMovement.IMPROVING,
    ): DimensionMovement.IMPROVING,
    (
        DimensionMovement.DETERIORATING,
        DimensionMovement.STABLE,
        DimensionMovement.DETERIORATING,
    ): DimensionMovement.DETERIORATING,
    (
        DimensionMovement.STABLE,
        DimensionMovement.DETERIORATING,
        DimensionMovement.DETERIORATING,
    ): DimensionMovement.DETERIORATING,
    (
        DimensionMovement.IMPROVING,
        DimensionMovement.DETERIORATING,
        DimensionMovement.DETERIORATING,
    ): DimensionMovement.DETERIORATING,
    (
        DimensionMovement.DETERIORATING,
        DimensionMovement.IMPROVING,
        DimensionMovement.DETERIORATING,
    ): DimensionMovement.DETERIORATING,
}


def classify_financial_performance_dimension_movement(
    field_movements: Mapping[str, DimensionMovement],
) -> DimensionMovement:
    """Classify Financial Performance dimension movement from 3 registered fields
    under MOM-FD-012.
    """

    rev = field_movements.get("period_revenue_total")
    exp = field_movements.get("period_expense_total")
    net = field_movements.get("period_net_result")

    if (
        rev is None
        or exp is None
        or net is None
        or rev is DimensionMovement.INSUFFICIENT_INFORMATION
        or exp is DimensionMovement.INSUFFICIENT_INFORMATION
        or net is DimensionMovement.INSUFFICIENT_INFORMATION
    ):
        return DimensionMovement.INSUFFICIENT_INFORMATION

    return COHERENT_MOVEMENTS.get(
        (rev, exp, net), DimensionMovement.INSUFFICIENT_INFORMATION
    )

