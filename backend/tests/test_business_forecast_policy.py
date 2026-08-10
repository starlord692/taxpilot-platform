"""Focused deterministic tests for FORECAST-004 Policy Evaluation."""

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from enum import StrEnum

import pytest

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
    ApplicabilityRule,
    BusinessForecastPolicyEvaluator,
    Comparison,
    ComparisonOperator,
    ConditionExpression,
    ConditionInputReference,
    ConditionOperand,
    ConditionStatus,
    EvaluationContext,
    PolicyAggregation,
    PolicyCondition,
    PolicyDefinition,
    StatusExpression,
    StatusHandling,
    StatusHandlingBehavior,
    StatusReference,
)


class HealthStatus(StrEnum):
    GOOD = "good"
    BAD = "bad"


def _time() -> datetime:
    return datetime(2026, 8, 10, tzinfo=UTC)


def _reference() -> ConditionInputReference:
    return ConditionInputReference(
        "PublishedForecast", "Business Health", "status", "enum"
    )


def _expression() -> ConditionExpression:
    return ConditionExpression(
        comparison=Comparison(
            _reference(),
            ComparisonOperator.EQUALS,
            ConditionOperand("enum", HealthStatus.GOOD),
        )
    )


def _context(value: object = HealthStatus.GOOD) -> EvaluationContext:
    return EvaluationContext(
        "context-1", _time(), uuid.uuid4(), ((_reference(), value),), ("evidence-1",)
    )


def _forecast(business_id: uuid.UUID | None = None) -> PublishedForecast:
    identity = ForecastIdentity(
        business_id=business_id or uuid.uuid4(),
        assessed_at=_time(),
        horizon=ForecastHorizon("90 days"),
        published_version="1",
    )
    traceability = ForecastTraceability(
        (ForecastSourceReference("Business Health", "h1", "p1", _time()),),
        "policy-1",
        ForecastExplanationReferences(("explanation-1",)),
    )
    forecast = BusinessForecast(
        identity,
        "projection",
        (ForecastAssumption("a1", "assumption", "p1"),),
        (ForecastLimitation("l1", "limitation", "p1"),),
        traceability,
        _time(),
    )
    return PublishedForecast(forecast, _time())


def _policy(
    behavior: StatusHandlingBehavior = StatusHandlingBehavior.CONSIDER,
) -> PolicyDefinition:
    condition = PolicyCondition(
        "c1", _expression(), ApplicabilityRule(ApplicabilityMode.ALWAYS), "founder"
    )
    rule = AggregationResultRule(
        StatusExpression(
            status_reference=StatusReference("c1", ConditionStatus.SATISFIED)
        ),
        ConditionStatus.SATISFIED,
    )
    aggregation = PolicyAggregation(("c1",), (StatusHandling("c1", behavior),), (rule,))
    return PolicyDefinition(
        "p1",
        "1",
        _time(),
        None,
        ApplicabilityRule(ApplicabilityMode.ALWAYS),
        (condition,),
        aggregation,
        "founder",
    )


def test_evaluator_preserves_satisfied_result_and_deterministic_aggregate() -> None:
    context = _context()
    evaluation = BusinessForecastPolicyEvaluator().evaluate(
        evaluation_id="e1",
        forecast=_forecast(context.business_id),
        policy=_policy(),
        context=context,
        evaluation_time=_time(),
    )
    assert evaluation.overall_status is ConditionStatus.SATISFIED
    assert evaluation.condition_results[0].status is ConditionStatus.SATISFIED
    assert (
        BusinessForecastPolicyEvaluator()
        .evaluate(
            evaluation_id="e1",
            forecast=_forecast(context.business_id),
            policy=_policy(),
            context=context,
            evaluation_time=_time(),
        )
        .overall_status
        is ConditionStatus.SATISFIED
    )


def test_missing_context_value_is_unavailable() -> None:
    context = EvaluationContext("context-1", _time(), uuid.uuid4(), (), ("evidence-1",))
    evaluation = BusinessForecastPolicyEvaluator().evaluate(
        evaluation_id="e1",
        forecast=_forecast(context.business_id),
        policy=_policy(),
        context=context,
        evaluation_time=_time(),
    )
    assert evaluation.condition_results[0].status is ConditionStatus.UNAVAILABLE
    assert evaluation.overall_status is ConditionStatus.UNAVAILABLE


def test_ignore_and_map_to_unavailable_do_not_change_condition_traceability() -> None:
    context = _context()
    evaluator = BusinessForecastPolicyEvaluator()
    ignored = evaluator.evaluate(
        evaluation_id="e1",
        forecast=_forecast(context.business_id),
        policy=_policy(StatusHandlingBehavior.IGNORE),
        context=context,
        evaluation_time=_time(),
    )
    mapped = evaluator.evaluate(
        evaluation_id="e1",
        forecast=_forecast(context.business_id),
        policy=_policy(StatusHandlingBehavior.MAP_TO_UNAVAILABLE),
        context=context,
        evaluation_time=_time(),
    )
    assert ignored.condition_results[0].status is ConditionStatus.SATISFIED
    assert mapped.condition_results[0].status is ConditionStatus.SATISFIED
    assert ignored.overall_status is ConditionStatus.UNAVAILABLE
    assert mapped.overall_status is ConditionStatus.UNAVAILABLE


def test_expression_composition_and_context_immutability() -> None:
    expression = ConditionExpression(not_=(ConditionExpression(any=(_expression(),)),))
    context = _context(HealthStatus.BAD)
    condition = PolicyCondition(
        "c1", expression, ApplicabilityRule(ApplicabilityMode.ALWAYS), "founder"
    )
    policy = _policy()
    policy = PolicyDefinition(
        policy.policy_id,
        policy.version,
        policy.effective_from,
        policy.effective_until,
        policy.applicability,
        (condition,),
        policy.aggregation,
        policy.provenance,
    )
    evaluation = BusinessForecastPolicyEvaluator().evaluate(
        evaluation_id="e1",
        forecast=_forecast(context.business_id),
        policy=policy,
        context=context,
        evaluation_time=_time(),
    )
    assert evaluation.overall_status is ConditionStatus.SATISFIED
    with pytest.raises(FrozenInstanceError):
        context.context_id = "replacement"  # type: ignore[misc]


def test_invalid_expression_and_status_handling_are_rejected() -> None:
    with pytest.raises(ValueError, match="exactly one form"):
        ConditionExpression()
    with pytest.raises(ValueError, match="must not be empty"):
        StatusExpression(all=())
    with pytest.raises(ValueError, match="status handling"):
        PolicyAggregation(("c1",), (), ())


def test_invalid_enum_value_and_unknown_type_are_unavailable_or_rejected() -> None:
    context = _context("good")
    evaluation = BusinessForecastPolicyEvaluator().evaluate(
        evaluation_id="e1",
        forecast=_forecast(context.business_id),
        policy=_policy(),
        context=context,
        evaluation_time=_time(),
    )
    assert evaluation.condition_results[0].status is ConditionStatus.UNAVAILABLE
    with pytest.raises(ValueError, match="not approved"):
        ConditionInputReference(
            "PublishedForecast", "Business Health", "status", "json"
        )
