"""Tests for the policy-only Business Momentum subcomponents."""

from decimal import Decimal
from typing import Any

from app.modules.momentum.policies import (
    BaselineEligibility,
    ComparisonCandidate,
    ComparisonKind,
    CurrencyCompatibility,
    DimensionMovement,
    RateClassification,
    WholeBusinessDirection,
    classify_field_movement,
    classify_financial_performance_dimension_movement,
    classify_financial_performance_rate,
    combine_direction,
    select_comparison,
)


def test_comparison_selection_is_deterministic_and_fail_closed() -> None:
    assert (
        select_comparison(
            (
                ComparisonCandidate(ComparisonKind.PRIOR_EQUIVALENT_PERIOD, True),
                ComparisonCandidate(ComparisonKind.PREVIOUS_COMPARABLE_PERIOD, True),
            )
        )
        is ComparisonKind.PREVIOUS_COMPARABLE_PERIOD
    )
    assert (
        select_comparison(
            (
                ComparisonCandidate(ComparisonKind.PREVIOUS_COMPARABLE_PERIOD, True),
                ComparisonCandidate(ComparisonKind.PREVIOUS_COMPARABLE_PERIOD, True),
            )
        )
        is ComparisonKind.NO_VALID_COMPARISON
    )


def test_direction_requires_three_valid_dimensions_and_strict_majority() -> None:
    assert (
        combine_direction(
            {
                "revenue": DimensionMovement.IMPROVING,
                "expense": DimensionMovement.STABLE,
            }
        )
        is WholeBusinessDirection.INSUFFICIENT_INFORMATION
    )
    assert (
        combine_direction(
            {
                "revenue": DimensionMovement.IMPROVING,
                "expense": DimensionMovement.IMPROVING,
                "cash": DimensionMovement.DETERIORATING,
            }
        )
        is WholeBusinessDirection.IMPROVING
    )
    assert (
        combine_direction(
            {
                "revenue": DimensionMovement.IMPROVING,
                "expense": DimensionMovement.DETERIORATING,
                "cash": DimensionMovement.STABLE,
            }
        )
        is WholeBusinessDirection.BROADLY_UNCHANGED
    )


def test_financial_performance_rate_uses_approved_bands_and_fails_closed() -> None:
    common: dict[str, Any] = {
        "baseline_eligibility": BaselineEligibility.ELIGIBLE,
        "currency_compatibility": CurrencyCompatibility.SAME_CURRENCY,
        "comparable": True,
        "evidence_valid": True,
    }
    assert (
        classify_financial_performance_rate(
            current=Decimal("105"), comparison=Decimal("100"), **common
        )
        is RateClassification.GRADUAL
    )
    assert (
        classify_financial_performance_rate(
            current=Decimal("120"), comparison=Decimal("100"), **common
        )
        is RateClassification.MODERATE
    )
    assert (
        classify_financial_performance_rate(
            current=Decimal("130"), comparison=Decimal("100"), **common
        )
        is RateClassification.RAPID
    )
    assert (
        classify_financial_performance_rate(
            current=Decimal("100"),
            comparison=Decimal("0"),
            **common,
        )
        is RateClassification.NOT_DETERMINABLE
    )
    assert (
        classify_financial_performance_rate(
            current=Decimal("100"),
            comparison=Decimal("100"),
            stable=True,
            **common,
        )
        is RateClassification.NOT_DETERMINABLE
    )


def test_classify_field_movement_semantics_and_polarity() -> None:
    compat = CurrencyCompatibility.SAME_CURRENCY

    # Revenue
    assert (
        classify_field_movement(
            field="period_revenue_total",
            current_amount=Decimal("150"),
            comparison_amount=Decimal("100"),
            materiality_outcome="MATERIAL",
            currency_compatibility=compat,
        )
        == DimensionMovement.IMPROVING
    )
    assert (
        classify_field_movement(
            field="period_revenue_total",
            current_amount=Decimal("80"),
            comparison_amount=Decimal("100"),
            materiality_outcome="MATERIAL",
            currency_compatibility=compat,
        )
        == DimensionMovement.DETERIORATING
    )

    # Expenses (Inverse Polarity)
    assert (
        classify_field_movement(
            field="period_expense_total",
            current_amount=Decimal("80"),
            comparison_amount=Decimal("100"),
            materiality_outcome="MATERIAL",
            currency_compatibility=compat,
        )
        == DimensionMovement.IMPROVING
    )
    assert (
        classify_field_movement(
            field="period_expense_total",
            current_amount=Decimal("150"),
            comparison_amount=Decimal("100"),
            materiality_outcome="MATERIAL",
            currency_compatibility=compat,
        )
        == DimensionMovement.DETERIORATING
    )

    # Net Result
    assert (
        classify_field_movement(
            field="period_net_result",
            current_amount=Decimal("50"),
            comparison_amount=Decimal("20"),
            materiality_outcome="MATERIAL",
            currency_compatibility=compat,
        )
        == DimensionMovement.IMPROVING
    )

    # Materiality = NOT_MATERIAL yields STABLE
    assert (
        classify_field_movement(
            field="period_revenue_total",
            current_amount=Decimal("10000"),
            comparison_amount=Decimal("100"),
            materiality_outcome="NOT_MATERIAL",
            currency_compatibility=compat,
        )
        == DimensionMovement.STABLE
    )

    # Fail closed on invalid / undeterminable
    assert (
        classify_field_movement(
            field="period_revenue_total",
            current_amount=None,
            comparison_amount=Decimal("100"),
            materiality_outcome="MATERIAL",
            currency_compatibility=compat,
        )
        == DimensionMovement.INSUFFICIENT_INFORMATION
    )


def test_classify_financial_performance_dimension_movement_coherence() -> None:
    # Coherent improving
    assert (
        classify_financial_performance_dimension_movement(
            {
                "period_revenue_total": DimensionMovement.IMPROVING,
                "period_expense_total": DimensionMovement.IMPROVING,
                "period_net_result": DimensionMovement.IMPROVING,
            }
        )
        == DimensionMovement.IMPROVING
    )

    # Coherent deteriorating
    assert (
        classify_financial_performance_dimension_movement(
            {
                "period_revenue_total": DimensionMovement.DETERIORATING,
                "period_expense_total": DimensionMovement.DETERIORATING,
                "period_net_result": DimensionMovement.DETERIORATING,
            }
        )
        == DimensionMovement.DETERIORATING
    )

    # Coherent stable
    assert (
        classify_financial_performance_dimension_movement(
            {
                "period_revenue_total": DimensionMovement.STABLE,
                "period_expense_total": DimensionMovement.STABLE,
                "period_net_result": DimensionMovement.STABLE,
            }
        )
        == DimensionMovement.STABLE
    )

    # Material Contradictions -> INSUFFICIENT_INFORMATION
    assert (
        classify_financial_performance_dimension_movement(
            {
                "period_revenue_total": DimensionMovement.IMPROVING,
                "period_expense_total": DimensionMovement.IMPROVING,
                "period_net_result": DimensionMovement.DETERIORATING,
            }
        )
        == DimensionMovement.INSUFFICIENT_INFORMATION
    )

    assert (
        classify_financial_performance_dimension_movement(
            {
                "period_revenue_total": DimensionMovement.DETERIORATING,
                "period_expense_total": DimensionMovement.DETERIORATING,
                "period_net_result": DimensionMovement.IMPROVING,
            }
        )
        == DimensionMovement.INSUFFICIENT_INFORMATION
    )
