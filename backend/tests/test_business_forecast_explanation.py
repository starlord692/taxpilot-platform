"""Tests for FORECAST-005 deterministic structured explanations."""

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from enum import StrEnum

import pytest

from app.modules.business_forecast.explanation import (
    BusinessForecastExplanationEngine,
    ExplanationFactType,
)
from app.modules.business_forecast.models import (
    BusinessForecast,
    ForecastAssumption,
    ForecastExplanationReferences,
    ForecastHorizon,
    ForecastIdentity,
    ForecastLimitation,
    ForecastSourceReference,
    ForecastTraceability,
    PublishedForecast,
)
from app.modules.business_forecast.policy import (
    AggregationResultRule,
    ApplicabilityMode,
    ApplicabilityOutcome,
    ApplicabilityRule,
    BusinessForecastPolicyEvaluator,
    Comparison,
    ComparisonOperator,
    ConditionExpression,
    ConditionInputReference,
    ConditionOperand,
    ConditionStatus,
    EvaluationContext,
    EvaluationImpact,
    PolicyAggregation,
    PolicyCondition,
    PolicyDefinition,
    PolicyEvaluation,
    StatusExpression,
    StatusHandling,
    StatusHandlingBehavior,
    StatusReference,
)


class Status(StrEnum):
    GOOD = "good"


def _time() -> datetime:
    return datetime(2026, 8, 12, tzinfo=UTC)


def _reference() -> ConditionInputReference:
    return ConditionInputReference("PublishedForecast", "Health", "status", "enum")


def _evaluation(
    value: object = Status.GOOD,
    behavior: StatusHandlingBehavior = StatusHandlingBehavior.CONSIDER,
    applicability: ApplicabilityRule | None = None,
) -> PolicyEvaluation:
    business_id = uuid.uuid4()
    identity = ForecastIdentity(business_id, _time(), ForecastHorizon("90 days"), "1")
    traceability = ForecastTraceability(
        (ForecastSourceReference("Business Health", "h1", "p1", _time()),),
        "forecast-policy",
        ForecastExplanationReferences(("e1",)),
    )
    forecast = PublishedForecast(
        BusinessForecast(
            identity,
            "projection",
            (ForecastAssumption("a", "assumption", "p"),),
            (ForecastLimitation("l", "limitation", "p"),),
            traceability,
            _time(),
        ),
        _time(),
    )
    expression = ConditionExpression(
        comparison=Comparison(
            _reference(),
            ComparisonOperator.EQUALS,
            ConditionOperand("enum", Status.GOOD),
        )
    )
    condition = PolicyCondition(
        "c1",
        expression,
        applicability or ApplicabilityRule(ApplicabilityMode.ALWAYS),
        "founder",
    )
    aggregation = PolicyAggregation(
        ("c1",),
        (StatusHandling("c1", behavior),),
        (
            AggregationResultRule(
                StatusExpression(
                    status_reference=StatusReference("c1", ConditionStatus.SATISFIED)
                ),
                ConditionStatus.SATISFIED,
            ),
        ),
    )
    policy = PolicyDefinition(
        "p",
        "1",
        _time(),
        None,
        ApplicabilityRule(ApplicabilityMode.ALWAYS),
        (condition,),
        aggregation,
        "founder",
    )
    context = EvaluationContext(
        "ctx", _time(), business_id, ((_reference(), value),), ("context-evidence",)
    )
    return BusinessForecastPolicyEvaluator().evaluate(
        evaluation_id="eval-1",
        forecast=forecast,
        policy=policy,
        context=context,
        evaluation_time=_time(),
    )


def test_explanation_preserves_authoritative_values_deterministically() -> None:
    evaluation = _evaluation()
    engine = BusinessForecastExplanationEngine()
    explanation = engine.explain(evaluation)
    assert explanation.evaluation_id == evaluation.evaluation_id
    assert explanation.overall_status is evaluation.overall_status
    assert explanation.generated_at == evaluation.evaluation_time
    assert explanation == engine.explain(evaluation)
    condition = explanation.condition_explanations[0]
    assert condition.applicability is ApplicabilityOutcome.APPLICABLE
    assert tuple(fact.fact_type for fact in condition.explanation_facts) == (
        ExplanationFactType.CONDITION_STATUS,
        ExplanationFactType.CONDITION_APPLICABILITY,
    )
    with pytest.raises(FrozenInstanceError):
        explanation.evaluation_id = "replacement"  # type: ignore[misc]


def test_unavailable_preserves_applicability_impact_and_single_reference() -> None:
    explanation = BusinessForecastExplanationEngine().explain(_evaluation(value="bad"))
    condition = explanation.condition_explanations[0]
    unavailable = condition.unavailable_information[0]
    assert condition.applicability is ApplicabilityOutcome.APPLICABLE
    assert condition.status is ConditionStatus.UNAVAILABLE
    assert unavailable.input_reference == _reference()
    assert unavailable.evaluation_impact is EvaluationImpact.CONDITION_UNAVAILABLE
    assert explanation.unavailable_information == condition.unavailable_information


def test_not_applicable_is_preserved_without_unavailable_information() -> None:
    unavailable_rule = ApplicabilityRule(
        ApplicabilityMode.WHEN,
        ConditionExpression(
            comparison=Comparison(
                _reference(),
                ComparisonOperator.EQUALS,
                ConditionOperand("enum", Status.GOOD),
            )
        ),
    )
    explanation = BusinessForecastExplanationEngine().explain(
        _evaluation(Status.GOOD, applicability=unavailable_rule)
    )
    assert explanation.condition_explanations[0].status is ConditionStatus.SATISFIED
